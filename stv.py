from __future__ import annotations
from typing import Dict, List, Iterable, Iterator, Tuple

import enum
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from operator import itemgetter
from itertools import takewhile


class InvalidBallotError(Exception):
    pass


class InvalidActionError(Exception):
    pass


class CountingError(Exception):
    pass


class TieError(CountingError):
    pass


class UnfilledSeatsError(CountingError):
    pass


@dataclass
class Candidate:
    name: str

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class Score:
    candidate: Candidate
    value: Fraction


class CountingBallot:
    def __init__(self, preference_list: List[Candidate]):
        if not preference_list or len(preference_list) != len(set(preference_list)):
            raise InvalidBallotError('empty or spoiled ballot')

        self.choices = preference_list
        self.value = Fraction(1)


class RoundAction(enum.Enum):
    ELECTED = enum.auto()
    ELECTED_BY_DEFAULT = enum.auto()
    ELIMINATED = enum.auto()

    def __str__(self) -> str:
        return self.name.replace('_', ' ').capitalize()


@dataclass
class Round:
    number: int
    scores: List[Score]
    action: RoundAction
    affected: List[Candidate]


@dataclass
class Summary:
    seats: int
    quota: int
    elected: List[Score]
    rounds: List[Round]

    @property
    def unfilled_seats(self) -> int:
        return self.seats - len(self.elected)


class Election:
    def __init__(
        self,
        seats: int,
        candidates: Iterable[Candidate],
        preference_lists: Iterable[List[Candidate]] = [],
    ):
        self.seats = seats
        self.candidates = set(candidates)
        self.valid_ballots: List[CountingBallot] = []
        self.spoiled_ballot_count = 0

        for preference_list in preference_lists:
            self.add_ballot(preference_list)

    def add_ballot(self, preference_list: List[Candidate]) -> None:
        try:
            ballot = CountingBallot(preference_list)
            self.valid_ballots.append(ballot)
        except InvalidBallotError:
            self.spoiled_ballot_count += 1

    def init_count(self) -> Count:
        return Count(self)


class Count:
    def __init__(self, election: Election):
        self.seats = election.seats

        self.alloc: Dict[Candidate, List[CountingBallot]] = {c: [] for c in election.candidates}
        for ballot in election.valid_ballots:
            self.alloc[ballot.choices[0]].append(ballot)

        self.rounds: List[Round] = []
        self.elected: List[Score] = []
        self.quota = (len(election.valid_ballots) // (self.seats + 1)) + 1

    def _elect(self, score: Score) -> None:
        surplus = score.value - self.quota

        if surplus == 0:
            # ballot values would end up being 0 so just drop them
            del self.alloc[score.candidate]
        else:
            multiplier = Fraction(surplus, self.quota)
            for ballot in self.alloc[score.candidate]:
                ballot.value *= multiplier
            self._redistribute_ballots(score.candidate)

        self.elected.append(score)

    def _redistribute_ballots(self, candidate: Candidate) -> None:
        for ballot in self.alloc.pop(candidate):
            try:
                while ballot.choices[0] not in self.alloc.keys():
                    ballot.choices.pop(0)

                self.alloc[ballot.choices[0]].append(ballot)
            except IndexError:
                # Ballot has now been exhausted, drop it
                pass

    def _do_round(self) -> Round:
        action: RoundAction
        affected: List[Candidate] = []

        open_seats = self.seats - len(self.elected)

        # Add up scores and sort them in descending order
        scores = [Score(c, sum((b.value for b in bs), Fraction(0))) for c, bs in self.alloc.items()]
        scores.sort(reverse=True, key=lambda s: s.value)

        if scores[0].value >= self.quota:
            # at least one candidate reached quota
            reached_quota = list(takewhile(lambda s: s.value >= self.quota, scores))
            if len(reached_quota) > open_seats:
                # more candidates reached quota than there are available
                # seats, take candidates with highest scores unless
                # there is a tie
                if reached_quota[open_seats].value == reached_quota[open_seats - 1].value:
                    raise TieError('tie between candidates to be elected')

                reached_quota = reached_quota[:open_seats]

            action = RoundAction.ELECTED

            for score in reached_quota:
                affected.append(score.candidate)
                self._elect(score)
        elif len(self.alloc) <= open_seats:
            # no one reached quota but candidates can win by default
            action = RoundAction.ELECTED_BY_DEFAULT
            for score in scores:
                affected.append(score.candidate)
                self._elect(score)
        else:
            # no one reached quota, eliminate candidates with the lowest score
            lowest_scores = takewhile(lambda s: s.value == scores[-1].value, reversed(scores))

            action = RoundAction.ELIMINATED
            for score in lowest_scores:
                affected.append(score.candidate)
                self._redistribute_ballots(score.candidate)

        round = Round(
            number=len(self.rounds) + 1,
            scores=scores,
            action=action,
            affected=affected,
        )
        self.rounds.append(round)
        return round

    @property
    def is_counting(self) -> bool:
        return len(self.elected) < self.seats and len(self.alloc) > 0

    def round_iter(self) -> Iterator[Round]:
        while self.is_counting:
            yield self._do_round()

    def get_summary(self) -> Summary:
        while self.is_counting:
            self._do_round()

        return Summary(seats=self.seats, quota=self.quota, elected=self.elected, rounds=self.rounds)

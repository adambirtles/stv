from __future__ import annotations
from typing import Dict, List, Tuple, Optional

from dataclasses import dataclass
from fractions import Fraction
import enum

@dataclass
class Candidate:
    name: str

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

Electee = Tuple[Candidate, Fraction]

class CountingBallot:
    def __init__(self, choices: List[Candidate]):
        if not choices or len(choices) != len(set(choices)):
            raise ValueError('empty or spoiled ballot')

        self.choices = choices
        self.value = Fraction(1)

    @classmethod
    def valid_ballot(cls, choices: List[Candidate]) -> Optional[CountingBallot]:
        try:
            return cls(choices)
        except ValueError:
            return None


class RoundAction(enum.Enum):
    ELECTED = enum.auto()
    ELECTED_BY_DEFAULT = enum.auto()
    ELIMINATED = enum.auto()


@dataclass
class Round:
    number: int
    scores: Dict[Candidate, Fraction]
    action: RoundAction
    affected: List[Candidate]


@dataclass
class Result:
    valid_ballots: int
    spoiled_ballots: int
    quota: int
    elected: List[Electee]
    rounds: List[Round]


class Allocation:
    def __init__(self, candidates: List[Candidate], ballots: List[CountingBallot]):
        self._alloc: Dict[Candidate, List[CountingBallot]] = {c: [] for c in candidates}
        for ballot in ballots:
            self._alloc[ballot.choices[0]].append(ballot)

    @property
    def scores(self) -> Dict[Candidate, Fraction]:
        return {c: sum((b.value for b in bs), Fraction(0)) for c, bs in self._alloc.items()}

    @property
    def remaining_candidates(self) -> int:
        return len(self._alloc)

    def elect_candidate(self, candidate: Candidate, score: Fraction, quota: int) -> None:
        surplus = score - quota

        if surplus == 0:
            del self._alloc[candidate]
            return

        multiplier = Fraction(surplus, quota)
        for ballot in self._alloc[candidate]:
            ballot.value *= multiplier

        self.remove_candidate(candidate)

    def remove_candidate(self, candidate: Candidate) -> None:
        for ballot in self._alloc.pop(candidate):
            try:
                while ballot.choices[0] not in self._alloc.keys():
                    ballot.choices.pop(0)

                self._alloc[ballot.choices[0]].append(ballot)
            except IndexError:
                pass


class Election:
    def __init__(self, seats: int, candidates: List[Candidate], ballots: List[List[Candidate]]):
        self.seats = seats
        self.candidates = candidates

        self.valid_ballots = list(filter(None, map(CountingBallot.valid_ballot, ballots)))
        self.spoiled_ballot_count = len(ballots) - len(self.valid_ballots)

        self.elected: List[Electee] = []
        self.rounds: List[Round] = []
        self.allocation = Allocation(candidates, self.valid_ballots)

        self.allow_defaulting = False

        self.quota = (len(self.valid_ballots) // (seats + 1)) + 1

    def _do_round(self) -> None:
        open_seats = self.seats - len(self.elected)

        scores = self.allocation.scores
        reached_quota = {c: s for c, s in scores.items() if s >= self.quota}
        if reached_quota:
            # at least one candidate reached quota
            if len(reached_quota) > open_seats:
                raise Exception('tie between candidates to be elected')

            action = RoundAction.ELECTED
            affected = list(reached_quota.keys())

            self.elected.extend(reached_quota.items())
            for candidate, score in reached_quota.items():
                self.allocation.elect_candidate(candidate, score, self.quota)
        elif self.allocation.remaining_candidates <= open_seats:
            # no one reached quota but candidates can win by default
            if not self.allow_defaulting:
                raise Exception('not enough candidates could reach quota to fill all seats')

            action = RoundAction.ELECTED_BY_DEFAULT
            affected = list(scores.keys())
            self.elected.extend(scores.items())
        else:
            # no one reached quota and a candidate must be eliminated
            min_score = min(scores.values())
            lowest_scoring = [c for c, s in scores.items() if s == min_score]

            if len(lowest_scoring) > 1:
                raise Exception('tie when eliminating candidates')

            action = RoundAction.ELIMINATED
            affected = lowest_scoring
            self.allocation.remove_candidate(lowest_scoring[0])

        self.rounds.append(Round(number=len(self.rounds),
                                 scores=scores,
                                 action=action,
                                 affected=affected
                                 ))

    def do_all_rounds(self) -> Result:
        while len(self.elected) < self.seats:
            self._do_round()

        return Result(len(self.valid_ballots), self.spoiled_ballot_count, self.quota, self.elected, self.rounds)

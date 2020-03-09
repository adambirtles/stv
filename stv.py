#!/usr/bin/env python3
"""STV election calculator."""

from typing import List, Dict, Optional, Tuple, Iterable

from dataclasses import dataclass
from fractions import Fraction
from operator import itemgetter

Candidate = str
Allocation = Dict[Candidate, List['Ballot']]


@dataclass
class Ballot:
    """A ballot."""

    choices: List[Candidate]
    value: Fraction = Fraction(1)

    @classmethod
    def from_row(cls, row: List[str], candidates: List[Candidate]) -> 'Ballot':
        """Create a Ballot from a CSV row."""
        choices: Dict[int, Candidate] = {}
        for n, c in zip(row, candidates):
            if not n:
                continue

            k = int(n)
            if k in choices:
                return cls([])
            choices[k] = c

        return cls([c for _, c in sorted(choices.items(), key=itemgetter(0))])

    def is_valid(self) -> bool:
        """Check if ballot is valid.

        A ballot is valid iff it is not empty and there are no duplicate
        preferences.
        """
        return (bool(self.choices)
                and len(self.choices) == len(set(self.choices)))

    def transfer(self, remaining: Iterable[Candidate]) -> Optional[Candidate]:
        """Transfer ballot to next remaining candidate."""
        try:
            while self.choices[0] not in remaining:
                self.choices.pop(0)
        except IndexError:
            return None

        return self.choices[0]

    @staticmethod
    def calc_score(ballots: List['Ballot']) -> Fraction:
        """Add up the values of ballots."""
        return sum((b.value for b in ballots), Fraction(0))


class TieError(Exception):
    """Exception raised where there is a tie in an election."""

    def __init__(self, candidates: List[Candidate], electing: bool):
        """Initialise TieError.

        candidates: The candidates that tied
        electing: Whether the tie happened when electing or eliminating
            candidates.
        """
        self.candidates = candidates
        self.electing = electing

    def __str__(self) -> str:
        candidate_list = ', '.join(self.candidates)
        if self.electing:
            return f'tie when electing: {candidate_list}'
        else:
            return f'tie when eliminating: {candidate_list}'


def calculate(seats: int, candidates: List[Candidate],
          ballots: List[Ballot]) -> List[Candidate]:
    """Calculate an STV election."""
    elected: List[Candidate] = []
    valid_ballots = [b for b in ballots if b.is_valid()]
    quota = (len(valid_ballots) // (seats + 1)) + 1

    print('Valid ballots:', len(valid_ballots))
    print('Spoiled ballots:', len(ballots) - len(valid_ballots))
    print('Quota:', quota)

    allocation: Allocation = {c: [] for c in candidates}
    for ballot in valid_ballots:
        allocation[ballot.choices[0]].append(ballot)

    round = 1

    while len(elected) < seats:
        print(f'\n=== Round {round}')

        if len(allocation) <= seats - len(elected):
            for candidate in allocation.keys():
                elected.append(candidate)
                print(f'Elected {candidate} by default')
            break

        scores = {c: Ballot.calc_score(bs) for c, bs in allocation.items()}
        print('Scores (to 5 d.p.):')
        for candidate, score in scores.items():
            print(f'  - {candidate}: {float(score):.5f}')

        reached_quota = [c for c, s in scores.items() if s >= quota]
        if reached_quota:
            if len(reached_quota) + len(elected) > seats:
                raise TieError(elected, True)

            for candidate in reached_quota:
                elected.append(candidate)
                print(f'Elected {candidate}')

                surplus = scores[candidate] - quota
                if surplus == 0:
                    del allocation[candidate]
                    continue

                multiplier = Fraction(surplus, quota)
                for ballot in allocation.pop(candidate):
                    ballot.value *= multiplier
                    recipient = ballot.transfer(allocation.keys())
                    if recipient is not None:
                        allocation[recipient].append(ballot)
        else:
            min_score = min(scores.values())
            lowest_scoring = [c for c, s in scores.items() if s == min_score]
            if len(lowest_scoring) > 1:
                raise TieError(lowest_scoring, False)

            eliminated = lowest_scoring[0]
            print(f'Eliminating {eliminated}')
            for ballot in allocation.pop(eliminated):
                recipient = ballot.transfer(allocation.keys())
                if recipient is not None:
                    allocation[recipient].append(ballot)

        round += 1

    return elected


if __name__ == '__main__':
    from csv import reader
    from sys import stdin

    csv_reader = reader(stdin)
    candidates = next(csv_reader)
    ballots = [Ballot.from_row(row, candidates) for row in csv_reader]

    elected = calculate(3, candidates, ballots)
    print('\nElected:', ', '.join(elected))

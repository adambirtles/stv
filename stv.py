#!/usr/bin/env python3
"""STV election calculator."""

from typing import List, Dict, Optional, Tuple, Iterable

from dataclasses import dataclass
from fractions import Fraction
from operator import itemgetter
import argparse

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

    def transfer(self, allocation: Allocation) -> None:
        """Transfer ballot to next remaining candidate."""
        try:
            while self.choices[0] not in allocation:
                self.choices.pop(0)

            allocation[self.choices[0]].append(self)
        except IndexError:
            pass

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

        scores = {c: Ballot.calc_score(bs) for c, bs in allocation.items()}
        print('Scores (to 5 d.p.):')
        for candidate, score in scores.items():
            print(f'  - {candidate}: {float(score):.5f}')

        if len(allocation) <= seats - len(elected):
            for candidate in allocation.keys():
                elected.append(candidate)
                if scores[candidate] >= quota:
                    print(f'Elected {candidate}')
                else:
                    print(f'Elected {candidate} by default')
            break

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
                    ballot.transfer(allocation)
        else:
            min_score = min(scores.values())
            lowest_scoring = [c for c, s in scores.items() if s == min_score]
            if len(lowest_scoring) > 1:
                raise TieError(lowest_scoring, False)

            eliminated = lowest_scoring[0]
            print(f'Eliminating {eliminated}')
            for ballot in allocation.pop(eliminated):
                ballot.transfer(allocation)

        round += 1

    return elected


if __name__ == '__main__':
    from csv import reader
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument('seats',
                        type=int,
                        default=1,
                        help='number of seats in election')
    parser.add_argument('file',
                        nargs='?',
                        type=argparse.FileType('r'),
                        default=sys.stdin,
                        help='CSV file containing ballots. (default: stdin)')
    args = parser.parse_args()

    if args.seats < 1:
        print('error: must have at least 1 seat', file=sys.stderr)
        sys.exit(1)

    csv_reader = reader(args.file)
    candidates = next(csv_reader)
    ballots = [Ballot.from_row(row, candidates) for row in csv_reader]

    try:
        elected = calculate(args.seats, candidates, ballots)
        print('\nElected:', ', '.join(elected))
    except TieError as e:
        print(e)

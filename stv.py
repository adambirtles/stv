#!/usr/bin/env python3
"""STV election calculator."""

from typing import List, Dict, Optional, Any, Iterable

from dataclasses import dataclass
from fractions import Fraction
from operator import itemgetter
import random
import enum
import argparse

Candidate = str
Allocation = Dict[Candidate, List['Ballot']]


def _list_str(l: Iterable[Any]) -> str:
    return ', '.join(map(str, l))


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
            while self.choices[0] not in allocation.keys():
                self.choices.pop(0)

            allocation[self.choices[0]].append(self)
        except IndexError:
            pass

    @staticmethod
    def calc_score(ballots: List['Ballot']) -> Fraction:
        """Add up the values of ballots."""
        return sum((b.value for b in ballots), Fraction(0))


class STVError(Exception):
    """Base class for Exceptions raised when counting STV."""
    def __init__(self, elected: List[Candidate]):
        """Initialise STVError."""
        self.elected = elected


class UnbreakableTieError(STVError):
    """Raised when there is a tie in an election."""
    def __init__(self, elected: List[Candidate], tied: List[Candidate],
                 electing: bool):
        """Initialise UnbreakableTieError."""
        super().__init__(elected)

        self.tied = tied
        self.electing = electing

    def __str__(self) -> str:
        candidate_list = _list_str(self.tied)
        if self.electing:
            return f'tie when electing: {candidate_list}'
        else:
            return f'tie when eliminating: {candidate_list}'


class UnfilledSeatsError(STVError):
    """Raised when seats are left unfilled."""
    def __init__(self, elected: List[Candidate], unfilled: int, reason: str):
        """Initialise UnfilledSeatsError."""
        super().__init__(elected)

        self.unfilled = unfilled
        self.reason = reason

    def __str__(self) -> str:
        return self.reason


class TieStrategy(enum.Enum):
    """Represents strategies for breaking ties."""
    NONE = enum.auto()
    RANDOM = enum.auto()
    FIRST_IN_ORDER = enum.auto()

    def break_tie(self, tied: List[Candidate]) -> Optional[Candidate]:
        """Break tie according to strategy."""
        print('Tie between:', _list_str(tied))
        print('Breaking tie with strategy:', self)
        if self == TieStrategy.RANDOM:
            return random.choice(tied)
        elif self == TieStrategy.FIRST_IN_ORDER:
            return sorted(tied)[0]
        else:
            return None

    def __str__(self) -> str:
        return self.name.replace('_', ' ').lower()


def calculate(seats: int,
              candidates: List[Candidate],
              ballots: List[Ballot],
              no_defaulting: bool = False,
              tie_strategy: TieStrategy = TieStrategy.NONE) -> List[Candidate]:
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
        to_elect = seats - len(elected)
        if len(allocation) == 0:
            raise UnfilledSeatsError(
                elected, seats - len(elected),
                'not enough candidates to fill all seats')

        print('\n=== Round', round)

        scores = {c: Ballot.calc_score(bs) for c, bs in allocation.items()}
        print('Scores (to 5 d.p.):')
        for candidate, score in scores.items():
            print(f'  - {candidate}: {float(score):.5f}')

        reached_quota = [c for c, s in scores.items() if s >= quota]
        if reached_quota:
            if len(reached_quota) > to_elect:
                tie_break_winner = tie_strategy.break_tie(reached_quota)
                if tie_break_winner is None:
                    raise UnbreakableTieError(elected, reached_quota, True)
                reached_quota = [tie_break_winner]

            for candidate in reached_quota:
                elected.append(candidate)
                print('Elected', candidate)

                surplus = scores[candidate] - quota
                if surplus == 0:
                    del allocation[candidate]
                    continue

                multiplier = Fraction(surplus, quota)
                for ballot in allocation.pop(candidate):
                    ballot.value *= multiplier
                    ballot.transfer(allocation)
        elif len(allocation) <= to_elect:
            if no_defaulting:
                raise UnfilledSeatsError(
                    elected, to_elect,
                    'not enough candidates could reach quota to fill all seats.'
                )

            for candidate in allocation.keys():
                elected.append(candidate)
                print('Elected', candidate, 'by default')
        else:
            min_score = min(scores.values())
            lowest_scoring = [c for c, s in scores.items() if s == min_score]
            if len(lowest_scoring) > 1:
                eliminated = tie_strategy.break_tie(lowest_scoring)
                if eliminated is None:
                    raise UnbreakableTieError(elected, lowest_scoring, False)
            else:
                eliminated = lowest_scoring[0]

            print('Eliminated', eliminated)
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
                        help='Number of seats in election.')
    parser.add_argument('file',
                        nargs='?',
                        type=argparse.FileType('r'),
                        default=sys.stdin,
                        help='CSV file containing ballots. (default: stdin)')
    parser.add_argument('--no-defaulting',
                        action='store_true',
                        help="Don't allow candidates to win by default.")
    args = parser.parse_args()

    if args.seats < 1:
        parser.error('must have at least 1 seat')

    csv_reader = reader(args.file)
    candidates = next(csv_reader)
    ballots = [Ballot.from_row(row, candidates) for row in csv_reader]

    try:
        elected = calculate(args.seats,
                            candidates,
                            ballots,
                            no_defaulting=args.no_defaulting,
                            tie_strategy=TieStrategy.FIRST_IN_ORDER)
        print('\nElected:', _list_str(elected))
    except STVError as e:
        print(f'\n{parser.prog}: error: {e}', file=sys.stderr)
        print('Elected before error:', _list_str(e.elected), file=sys.stderr)
        sys.exit(1)

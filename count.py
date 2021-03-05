#!/usr/bin/env python3

from typing import Set, TextIO, Iterator

import argparse
import csv
from sys import stdin, stderr
from typing import Optional

import stv

parser = argparse.ArgumentParser(
    description='Count votes',
    epilog='''The first row of the CSV file should be a list of
    candidates and each subsequent row should be each ballot as a list
    of preferences.
    ''',
)

parser.add_argument(
    'seats',
    type=int,
    help='Number of seats being elected',
)

parser.add_argument(
    'file',
    type=argparse.FileType('r'),
    help='CSV file as described below.',
    default=stdin,
    nargs='?',
)

args = parser.parse_args()

csvreader = csv.reader(args.file)

candidates = {name: stv.Candidate(name) for name in next(csvreader)}

election = stv.Election(seats=3, candidates=candidates.values())

for row in csvreader:
    election.add_ballot([candidates[name] for name in row if name])

count = election.init_count()
print('Quota is', count.quota)
print()

for round in count.round_iter():
    print('# Round', round.number)

    print('Scores:')
    for score in round.scores:
        print(f'  - {score.candidate}: {float(score.value):.2f}')

    print(f'{round.action}: {", ".join(c.name for c in round.affected)}')

    print()

summary = count.get_summary()

print('# Summary')
print(f'Elected (Surplus):')
for score in summary.elected:
    print(f'  - {score.candidate} ({float(score.value - summary.quota):+.2f})')

if summary.unfilled_seats:
    print(f'There is/are {summary.unfilled_seats} unfilled seat(s)!')
else:
    print('All seats are filled :)')

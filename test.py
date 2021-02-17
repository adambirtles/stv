from typing import List, Optional
import csv

from stv import Candidate, Election

candidates: List[Candidate] = []
ballots: List[List[Candidate]] = []

with open('election.csv') as fp:
    reader = csv.reader(fp)
    candidates = list(map(Candidate, next(reader)))
    for row in reader:
        choices: List[Optional[Candidate]] = [None for _ in range(len(candidates))]

        for (n, cell) in enumerate(row):
            if not cell:
                continue

            pref = int(cell) - 1
            if choices[pref] != None:
                raise Exception("Duplicate vote")

            choices[pref] = candidates[n]

        ballots.append(list(filter(None, choices)))


election = Election(3, candidates, ballots)
results = election.do_all_rounds()

print(f'Quota: {results.quota}\n')

for round_ in results.rounds:
    print('# Round', round_.number)

    print('Scores:')
    for candidate, score in round_.scores.items():
        print(f'- {candidate}: {float(score):.2f}')

    print(f'{round_.action.name}: {", ".join(map(str, round_.affected))}')
    print()

print(results.elected)

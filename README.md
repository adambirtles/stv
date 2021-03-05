# STV

Implementation of Single Transferable Vote in Python.

## `count.py`

`count.py` is a script making use of STV.

```
usage: count.py [-h] seats [file]

Count votes

positional arguments:
  seats       Number of seats being elected
  file        CSV file as described below.

optional arguments:
  -h, --help  show this help message and exit

The first row of the CSV file should be a list of candidates and each subsequent
row should be each ballot as a list of preferences.
```

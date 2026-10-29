# NOTICE

## Data

This project uses the **Statlog (German Credit Data)** dataset:

> Hofmann, H. (1994). Statlog (German Credit Data) [Dataset]. UCI Machine Learning
> Repository. https://doi.org/10.24432/C5NC77

Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode),
as stated on the [UCI dataset page](https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data)
(checked 2026-10-29).

- The raw file is **not committed**. `make data` downloads it and verifies its SHA-256
  (`b21f3d81…5871`, pinned in `src/credit/pipeline/data.py`).
- Changes made: class recoded from 1 = good / 2 = bad to `bad` = 0 / 1; category codes
  mapped to readable labels.
- `data/queue.json` is a derived work: 60 benchmark rows, resampled with seeded
  perturbations of loan duration and amount. These records are synthetic demo inputs, not
  anonymised real people, and carry no outcome labels.
- The course copies of this dataset in other repositories are **not** used.

## Regulatory text

The ECOA notice paragraph in `src/credit/notice/__init__.py` follows
12 CFR 1002.9(b)(1) (Regulation B), a US federal regulation in the public domain, as
published on eCFR (checked 2026-10-29).

## Not advice

A portfolio demonstration. Not a lending system, not compliance advice, not legal advice.

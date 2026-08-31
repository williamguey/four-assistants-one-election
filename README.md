# four-assistants-one-election

Reproduction package for *Four Assistants, One Election: A Cross-Sectional Audit of
Web-Connected AI in Brazil's 2026 Presidential Race*.

## Requirements

Python 3.11+. `pip install requests pyyaml tenacity pandas numpy matplotlib`

## Data

- `data/raw/2026-09-w1/` raw responses, citations, collection manifest (append-only JSONL)
- `data/judged/2026-09-w1/` judge labels (provisional) and second-judge sample
- `data/probes/`, `data/wrappers/`, `data/outlet_registry.csv` probe and annotation inputs
- `outputs/2026-09-w1/` scored outcomes
- `data/raw/pilot/`, `data/raw/dryrun/` pipeline-validation runs, excluded from all analyses

## Reproduce from released data (no API key needed)

```
python manage.py test                # offline self-checks
python manage.py score 2026-09-w1    # scoring from judged labels
python manage.py analyze 2026-09-w1  # report
python paper/make_figs.py            # paper figures
```

## Re-collect or re-judge (calls paid APIs)

Create `.env` with `OPENROUTER_API_KEY=...`, then:

```
python manage.py estimate full
python manage.py collect --confirm-prereg
python manage.py judge 2026-09-w1 --second
```

Collection is deterministic given the seed in `config/config.yaml` (20261004) up to
provider-side nondeterminism. Prompts are assembled as prefix + fixed body + suffix;
all draws are seeded hashes (see `src/collect.py`).

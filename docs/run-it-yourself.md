# Run it yourself

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
make install        # Python and frontend dependencies
make run            # API on :8000, web on :3000
```

The trained model, its evidence and the synthetic queue are committed, so `make run` works immediately; the API seeds an empty database from `data/queue.json` on first start.

## Enable the analyst (optional)

Create `.env` (git-ignored) with `CREDIT_`-prefixed variables. To reuse the keys from `clinical_care_navigator`:

```bash
sed 's/^NAVIGATOR_/CREDIT_/' ../clinical_care_navigator/.env > .env
```

then delete lines you don't need. The variables used are listed in [Deploy](deploy.md#environment). Without `CREDIT_OPENAI_API_KEY` the analyst is disabled and everything else still works.

## Reproduce the evidence

```bash
make data           # download the UCI file and verify its SHA-256
make train          # writes artifacts/model.joblib and artifacts/evidence.json (~1 min)
make eval           # model gate, verifier mutations, meta-mutation, analyst stand-in
make reproduce      # retrain from scratch and require identical evidence
make docs-assets    # regenerate plots and docs/evidence/results.md
```

## Quality gates

```bash
make lint typecheck imports test   # ruff, mypy --strict, import contracts, pytest (coverage ≥ 90%)
cd frontend && npx tsc --noEmit && npm run build
```

End-to-end tests need the API running against a throwaway database:

```bash
make queue-reset    # DESTRUCTIVE: rebuilds the queue and clears analyst threads
CREDIT_DB_PATH=/tmp/e2e.db uv run uvicorn credit.api.main:app --port 8000 &
cd frontend && npx playwright test   # light, dark and mobile
make screenshots                     # docs/assets/screenshots/{light,dark}
```

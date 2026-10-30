.PHONY: install run dev test lint typecheck imports eval check data train queue queue-reset reproduce up down docs docs-build docs-assets frontend-install frontend-dev frontend-build frontend-types frontend-e2e screenshots

install:
	uv sync --extra dev --extra docs
	cd frontend && npm ci

# API on :8000 and frontend on :3000; Ctrl-C stops both.
run:
	@[ -d frontend/node_modules ] || (cd frontend && npm ci)
	@trap 'kill 0' INT TERM EXIT; \
	uv run uvicorn credit.api.main:app --port 8000 --timeout-graceful-shutdown 2 & \
	(cd frontend && npm run dev) & \
	wait

dev:
	uv run uvicorn credit.api.main:app --reload --port 8000

test:
	uv run pytest -q --cov

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

imports:
	PYTHONPATH=src uv run lint-imports

# Model gate + verifier gate (mutations, meta-mutation) + analyst gate (scripted stand-in).
eval:
	uv run python -m evals.run

check: lint typecheck imports test eval

# Downloads and verifies the UCI file (sha256-pinned).
data:
	uv run python -c "from credit.pipeline.data import load; print(len(load()), 'rows verified')"

# Writes artifacts/model.joblib and artifacts/evidence.json.
train:
	uv run python -m credit.pipeline.train

queue:
	uv run python -m credit.pipeline.queue

# Destructive: rebuilds the review queue and clears analyst threads.
queue-reset:
	uv run python -m credit.cli

# Retrain from scratch and confirm the committed evidence is reproduced (run date aside).
reproduce:
	cp artifacts/evidence.json /tmp/credit-evidence.json
	cp artifacts/model.joblib /tmp/credit-model.joblib
	$(MAKE) train
	uv run python -c "import json; a, b = (json.load(open(p)) for p in ('/tmp/credit-evidence.json', 'artifacts/evidence.json')); [d['provenance'].pop('run_date') for d in (a, b)]; assert a == b, 'evidence changed'; print('evidence reproduced')"
	cp /tmp/credit-evidence.json artifacts/evidence.json
	cp /tmp/credit-model.joblib artifacts/model.joblib

up:
	docker compose up --build

down:
	docker compose down

docs:
	uv run mkdocs serve -a localhost:8001

docs-build:
	uv run mkdocs build --strict

docs-assets:
	uv run python docs/generate_plots.py

frontend-install:
	cd frontend && npm ci

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-types:
	uv run python -c "from credit.api.main import app; import json; json.dump(app.openapi(), open('frontend/openapi.json', 'w'), indent=2)"
	cd frontend && npm run gen:types

frontend-e2e:
	cd frontend && npx playwright test

screenshots:
	cd frontend && npx playwright test capture-screenshots.spec.ts

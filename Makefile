SHELL := /bin/bash
# Homebrew's Node 22 is keg-only; do not alter the user's global shell config.
export PATH := $(CURDIR)/.tools:/opt/homebrew/opt/node@22/bin:$(PATH)

.PHONY: setup api web check test build e2e eval docker infra-init infra-plan
setup:
	uv sync --frozen
	cd apps/web && npm ci
	test -f .env || cp .env.example .env
api:
	uv run uvicorn builder_cup.main:create_app --factory --reload --host 127.0.0.1 --port 8000
web:
	cd apps/web && npm run dev
check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	cd apps/web && npm run typecheck
test:
	uv run pytest -q
build:
	cd apps/web && npm run build
e2e: build
	cd apps/web && npx playwright test
eval:
	uv run python scripts/evaluate.py
docker:
	docker compose up --build
infra-init:
	bash scripts/bootstrap-gcp.sh
infra-plan:
	terraform -chdir=infra/gcp plan

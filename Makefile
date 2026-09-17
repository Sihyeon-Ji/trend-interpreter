SHELL := /bin/bash
.DEFAULT_GOAL := help
# Homebrew's Node 22 is keg-only; do not alter the user's global shell config.
export PATH := $(CURDIR)/.tools:/opt/homebrew/opt/node@22/bin:$(PATH)
TERRAFORM := $(if $(wildcard $(CURDIR)/.tools/terraform),$(CURDIR)/.tools/terraform,terraform)

.PHONY: help setup api web check test build e2e eval eval-live docker infra-check infra-init infra-apply infra-plan
help:
	@printf '%s\n' 'Local: setup api web check test build e2e docker' 'Evaluation: eval (mock only), eval-live (configured provider; may incur API charges)' 'Infrastructure: infra-check (local validation), infra-plan (reads cloud state), infra-apply (creates/changes cloud resources)'
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
	MODEL_PROVIDER=mock uv run python scripts/evaluate.py
eval-live:
	uv run python scripts/evaluate.py
docker:
	docker compose up --build
infra-init:
	@printf '%s\n' 'This command previously applied cloud resources. Use infra-check for validation or infra-apply for provisioning.'
	@exit 2
infra-check:
	$(TERRAFORM) -chdir=infra/gcp fmt -check
	$(TERRAFORM) -chdir=infra/gcp init -backend=false -lockfile=readonly
	$(TERRAFORM) -chdir=infra/gcp validate
infra-apply:
	bash scripts/bootstrap-gcp.sh
infra-plan:
	$(TERRAFORM) -chdir=infra/gcp plan

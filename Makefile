.DEFAULT_GOAL := help
.PHONY: help install up down reset fmt lint tf-fmt tf-validate tf-sec test ci

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install dependencies
	uv sync
	uv run pre-commit install

up:  ## Start LocalStack and wait for readiness
	docker compose up -d
	@echo "Waiting for LocalStack..."
	@until curl -s http://localhost:4566/_localstack/health > /dev/null; do sleep 2; done
	@echo "LocalStack ready."

down:  ## Stop LocalStack
	docker compose down

reset: down up  ## Restart from a clean state

fmt:  ## Format Python
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Lint Python
	uv run ruff check .
	uv run ruff format --check .

tf-fmt:  ## Check Terraform formatting
	terraform -chdir=part1_infrastructure/local fmt -check -recursive ..

tf-validate:  ## Validate Terraform
	terraform -chdir=part1_infrastructure/local init -backend=false
	terraform -chdir=part1_infrastructure/local validate

tf-sec:  ## Static security scan of Terraform
	trivy config part1_infrastructure/

test:  ## Run tests
	uv run pytest -v

ci: lint tf-fmt tf-validate tf-sec test  ## Everything CI runs

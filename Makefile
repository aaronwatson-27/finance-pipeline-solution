.DEFAULT_GOAL := help

.PHONY: help install up down reset check-port fmt lint ls-landing ls-curated tf-fmt \
		tf-validate tf-sec tf-apply tf-plan-aws tf-apply-aws tf-destroy-aws test test-aws ci

AWSLOCAL = AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
           AWS_DEFAULT_REGION=ap-southeast-2 \
           aws --endpoint-url=http://localhost:4566

PY = PYTHONPATH=part2_pipeline/src uv run python

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install dependencies
	uv sync
	uv run pre-commit install

check-port:  ## Fail early if port 4566 is already in use
	@if lsof -i :4566 -sTCP:LISTEN -t > /dev/null 2>&1; then \
		echo "Port 4566 in use. Run 'docker ps' and stop the container holding it."; \
		exit 1; \
	fi

up: check-port  ## Start LocalStack and wait for readiness
	docker compose up -d --remove-orphans
	@echo "Waiting for LocalStack..."
	@until curl -s http://localhost:4566/_localstack/health > /dev/null; do sleep 2; done
	@echo "LocalStack ready."

down:  ## Stop LocalStack
	docker compose down

reset: down up  ## Restart LocalStack from a clean state

fmt:  ## Format Python
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Lint Python
	uv run ruff check .
	uv run ruff format --check .

tf-fmt:  ## Check Terraform formatting
	terraform fmt -check -recursive part1_infrastructure/

tf-validate:  ## Validate Terraform in both environments
	terraform -chdir=part1_infrastructure/local init -backend=false
	terraform -chdir=part1_infrastructure/local validate
	terraform -chdir=part1_infrastructure/aws init -backend=false
	terraform -chdir=part1_infrastructure/aws validate

tf-sec:  ## Static security scan (fails on HIGH and above)
	trivy config --exit-code 1 --severity HIGH,CRITICAL \
		--ignorefile .trivyignore \
		--tf-vars part1_infrastructure/local/terraform.tfvars \
		part1_infrastructure/local

tf-apply:  ## Provision local infrastructure in LocalStack
	terraform -chdir=part1_infrastructure/local init -input=false
	terraform -chdir=part1_infrastructure/local apply -auto-approve

tf-plan-aws:  ## Plan against real AWS
	terraform -chdir=part1_infrastructure/aws init -input=false
	terraform -chdir=part1_infrastructure/aws plan

tf-apply-aws:  ## Provision real AWS infrastructure (prompts for confirmation)
	terraform -chdir=part1_infrastructure/aws init -input=false
	terraform -chdir=part1_infrastructure/aws apply

tf-destroy-aws:  ## Tear down real AWS infrastructure
	terraform -chdir=part1_infrastructure/aws destroy

test:  ## Run tests (excludes tests requiring real AWS)
	uv run pytest -v -m "not aws"

test-aws:  ## Run tests that require real AWS credentials
	uv run pytest -v -m aws

ci: lint tf-fmt tf-validate tf-sec test  ## Everything CI runs

ls-landing:  ## List objects in the landing bucket
	@$(AWSLOCAL) s3 ls s3://finance-data-landing/ --recursive

ls-curated:  ## List objects in the curated bucket
	@$(AWSLOCAL) s3 ls s3://finance-data-curated/ --recursive

ingest:  ## Land raw transactions for a date (DATE=YYYY-MM-DD)
	@$(PY) -m finance_platform.ingest $(DATE)

# Finance Data Platform

A local prototype of a multi-tenant finance data platform. Uses terraform-provisioned S3
storage with role-based access control, and an orchestrated pipeline that ingests daily
transactions, validates them, quarantines what fails, and writes partitioned Parquet
aggregates to a curated layer.

Everything runs on a laptop against LocalStack. The same Terraform targets real AWS, which is
used to verify IAM policy enforcement.

---

## Quick start

Prerequisites: Docker desktop, [uv](https://docs.astral.sh/uv/), Terraform, trivy, tflint, and a
[LocalStack](https://localstack.cloud) auth token (free Hobby tier).

A LocalStack auth token is required — the container won't start without one.

```bash
cp .env.example .env          # add your LOCALSTACK_AUTH_TOKEN
make install                  # venv, dependencies, git hooks
make up                       # start LocalStack
make tf-apply                 # provision buckets and IAM roles
make run DATE=2026-08-18      # run the pipeline for one business date
```

Or the same steps in one command after setting up .env, run:

```bash
make demo DEMO_DATE=2026-08-18   # up + tf-apply + run + ls-landing + ls-curated
```

Then to confirm what was produced, run:

```bash
make ls-landing               # raw CSV and quarantined rejects
make ls-curated               # partitioned Parquet aggregates
```

Adding real AWS to .env is optional. It is needed only for `make test-aws`.

**One thing to note:** LocalStack Hobby has no state persistence, so `make down` destroys the buckets while Terraform state still records them. `make tf-apply` must be run after every `make up` — it drops the missing resources from the state file, and recreates them.

---

## What it builds

```
  fetch_transactions          ← stands in for an API, SFTP drop, or DB replica
         │
         ▼
  s3://finance-data-landing/landing/finance/transactions/dt=YYYY-MM-DD/
         │                     raw payload, stored exactly as received
         ▼
  quality gate (Pydantic)  ──► quarantine/finance/transactions/dt=.../rejects.csv
         │                     rejected rows + reason, replayable
         ▼
  DuckDB aggregation
         │
         ▼
  s3://finance-data-curated/curated/finance/daily_category_spend/
      transaction_date=YYYY-MM-DD/category=<category>/*.parquet
```

There are three data layers:

| Layer | Contents |
|---|---|
| Landing | Raw daily transaction CSV, unmodified |
| Staging | Validated rows, in memory, never persisted |
| Curated | Daily aggregates by category, partitioned Parquet |

Two types of defect are caught by the quality gate: structural (missing primary key, non-numeric
amount, unparseable date) and business rule (non-positive amount, duplicate primary key).
Rejects add a `reject_reason` to the full original record, so quarantine is replayable
rather than a log line.
Quarantined files are written to the landing bucket rather than curated. The finance_analyst role can only read curated, so rejected records, which hold the same sensitive data as valid ones, are still unreachable. Files are written to quarantine/finance/transactions/dt={date}/rejects.csv for inspection and replay.


### Infrastructure

For each specified domain, a landing and a curated bucket are created, each with SSE-S3 encryption, all public access blocked, versioning enabled, and lifecycle rules. Landing files expire after 30 days, curated objects are not expired but any superseded versions expire after 30 days.

Also two IAM roles are provisioned:

| Role | Access |
|---|---|
| `data_engineer` | Can read/write across every bucket in every provisioned domain |
| `finance_analyst` | Has `GetObject` and `ListBucket` on `finance-data-curated` only |

### Idempotency

Re-running a business date produces the same result rather than accumulating data.

- The run date is a flow parameter — nothing inside the flow reads the clock.
- Landing keys are derived from the date alone, so a re-run replaces one object rather than writing
  a second.
- Curated writes delete the target date partition before uploading, across all categories
  within it — so a category that disappears from the source doesn't leave a stale file behind.
- Only the run date's partition is touched.
- For testing, data is generated using a fixed RNG seed, so the same date will always produce identical input.

### Failure handling

The pipeline treats different failures differently, based on whether retrying could change the outcome.

- **Retries are only applied to network tasks** (fetch, S3 reads and writes). These can fail transiently and often succeed on the next attempt. The quality gate is deterministic — if it fails once it will fail again with the same input, so no retries.
- **Bad rows are quarantined, not treated as fatal.** A row that fails validation is written to `quarantine/…/rejects.csv` with a reason attached, and the run continues. One malformed row does not cause the entire pipeline to fail.
- **An empty quarantine file is still written** when there are no rejects, so a missing file clearly means the run did not complete rather than being ambiguous between "clean run" and "never ran".
- **Curated waits on quarantine** via a Prefect `wait_for` dependency. If the rejects file fails to persist after retries, the curated write is skipped entirely — a "successful" run should have both files or neither.

### IAM Policies

The finance_analyst and data_engineer roles are given only the actions they actually need - according to least privilege principles. Everything else is blocked automatically.

**The policies were verified against real AWS.** LocalStack's free tier does not enforce IAM. `make test-aws` assumes the analyst role and confirms it can list curated, but cannot list landing and cannot write to curated.

```
AccessDenied: User: arn:aws:sts::<account>:assumed-role/finance_analyst/pytest-least-privilege
is not authorized to perform: s3:ListBucket on resource:
"arn:aws:s3:::<prefix>finance-data-landing" because no identity-based policy allows the
s3:ListBucket action
```

---

## Extending it

### Adding a domain

To add a domain, this is a one line change in `part1_infrastructure/local/terraform.tfvars`:

```hcl
domains = {
  finance = {}
  sales   = {}
}
```

The `data_engineer` policy automatically enables access to new domain buckets, because its resource list is built by looping over module outputs.

### Adding another IAM role

Roles live in each environment's `main.tf` rather than a module. If this grew to a lot more, we might consider a `roles` variable holding a map of role name to `{ domains, layers, access }` and a single `for_each`.

### Adding another dataset

`s3.py`, `quality.py` and `config.py` are essentially domain-agnostic and can be reused easily.
Currently there is some coupling to the transactions dataset in `transform.py`, `ingest.py` and the flow. A future step could be generalising these.

### Adding another curated model

The aggregation currently lives in `sql/daily_category_spend.sql`. A second model needs a second SQL file and the partition columns and prefix parameterised — currently both inlined in
`transform.py`. At four or five models, it would probably make sense to switch to dbt.

---

## Make targets

| | |
|---|---|
| `make help` | Lists every target |
| `make install` | Create venv, install dependencies and git hooks |
| `make up` / `down` / `reset` | Start, stop, or restart LocalStack |
| `make check-port` | Fails with a readable message if 4566 is occupied |
| `make tf-apply` | Provision the local infrastructure |
| `make run DATE=YYYY-MM-DD` | Run the pipeline for one business date |
| `make demo DEMO_DATE=YYYY-MM-DD` | End-to-end: `up` + `tf-apply` + `run` + list both buckets |
| `make ls-landing` / `ls-curated` | Inspect S3 without credential setup |
| `make fmt` / `lint` | Format or check Python |
| `make tf-fmt` / `tf-validate` / `tf-sec` | Terraform formatting, validation, security scan |
| `make test` / `test-aws` | See below |
| `make ci` | Everything CI would run |


### Pre-commit hooks

- Pre-commit hooks catch formatting problems before they get committed: trailing whitespace and missing final newlines, accidentally staged private keys, invalid YAML, Python style issues (via ruff), and Terraform formatting and best-practice checks (via terraform fmt and tflint).
- terraform validate isn't a hook because it needs an initialised directory and would fail on a fresh clone - it runs via make tf-validate instead and covers both environments.
- trivy config scans the Terraform for security issues and fails the build on HIGH or CRITICAL findings. Two issues are deliberately accepted with justifications in .trivyignore - access logging and the SSE-S3 encryption.

---

## Testing

```bash
make test          # everything that runs locally (skips real-AWS tests)
make test-aws      # requires real AWS and applied aws/ infrastructure
```

| Test File | What it establishes |
|---|---|
| `test_seed.py` | Seed data is deterministic and each defect type is present. |
| `test_quality.py` | Each defect class is classified correctly, rejected rows keep every original field, and a row with two problems reports both |
| `test_idempotency.py` | Two runs of a date produce identical curated output, the landing object is replaced not duplicated, and other dates are untouched |
| `test_iam.py` | The analyst role can read curated, cannot read landing, cannot write to curated |

---

## Decisions and trade-offs

| Decision | Locally | In production |
|---|---|---|
| LocalStack for S3 | Free, fast, resettable, no cloud account needed for the dev loop | Real AWS, with LocalStack retained for CI integration tests |
| DuckDB as compute engine | Single process, no cluster, sub-second startup. Fine at this data size | Spark once data exceeds a certain volume. |
| No dbt | Transformation is one model, no need for dbt | Switch to dbt from the 2nd or 3rd onward, which would provide lineage and docs |
| Prefect for orchestration | Flows are Python, invoked directly | Same tool, deployed on a schedule and executed on shared infrastructure — the pipeline runs itself daily instead of waiting for someone to type make run.|
| Pydantic row-by-row validation | Per-row Pydantic errors give rich reject reasons |  Fast enough at this volume; at millions of rows a day, checking one row at a time in Python becomes the bottleneck. Swap in a batch validator, or let the SQL engine enforce the schema at load time |
| SSE-S3 rather than SSE-KMS | Specified by the brief; no key management overhead | SSE-KMS with a customer-managed key |
| No S3 access logging | Needs a destination bucket LocalStack can't meaningfully populate | Access logging to a dedicated bucket, or CloudTrail data events |

---

## AI usage

Claude (Anthropic) was used for the following:

- **First drafts** — the Terraform module, the IAM policy documents, and initial versions of
  each pipeline module, which I then reviewed and changed.
- **Debugging** — a Docker DNS failure, a `uv` PATH issue, and several signature mismatches during refactoring.
- **Verifying current tool behaviour** — LocalStack's auth token requirement and IAM
  enforcement tiers, and tfsec's deprecation in favour of Trivy, were checked against current
  documentation rather than taken from training data.
- **Documentation and the README.md** — drafted documentation, which I then updated.

# AGENTS.md: Regret Radar

## Project
Regret Radar is a hackathon project (track: Customers, Channels & Demand).
It unifies fragmented retail customer records into one identity, then scores
three risks and turns them into a ranked daily action list in rupees:
1. Stock-outs (customer couldn't buy)
2. Returns that erode margin (customer bought wrong)
3. Silent churn signals in support tickets (customer quietly left)

Headline metric: **Regret Score** = rupees lost or at risk per customer, SKU and store.

## Hard constraints (never violate)
- **Exasol Personal is the ONLY data platform.** All heavy compute (identity
  matching, forecasting, return scoring, ticket NLP, score aggregation) runs
  INSIDE Exasol via SQL and Python UDFs. Python outside the database is only
  for orchestration, data loading and the UI.
- **Public or synthetic data only.** No employer data, nothing proprietary.
- **Licence: MIT.** Keep LICENSE at the repo root. Add only compatible dependencies.
- **Original work.** Do not copy code from other projects without attribution
  and a compatible licence.
- **No secrets in git.** Credentials live in `.env` (gitignored). Keep
  `.env.example` up to date with placeholder values only.
- **Never run destructive or costly cloud commands without asking me first**:
  `exasol destroy`, `exasol install`, deleting schemas or tables,
  force-pushing. Always show the command and wait for approval.

## Data rules (this saves tokens)
- NEVER write data rows in chat or hand-write sample datasets.
- Data is produced by a seeded, vectorized local script (numpy/pandas/Faker).
  Same seed must give identical output.
- Support-ticket text comes from templates and phrase banks, not LLM calls.
- Generator supports `--scale small|medium|large` (about 100k / 5M / 50M events).
- Keep a ground-truth table so match, forecast and churn quality can be measured.
- Document every table and column in `docs/DATA.md`.

## Exasol rules
- Before writing Exasol SQL, UDFs, script language containers (SLC) or
  BucketFS code, **read the Exasol agent skills in `.agent/skills/`** (or
  `.agents/skills/`) and consult the official docs at docs.exasol.com.
  Do not guess Exasol syntax from other databases (Postgres, MySQL).
- UDFs are Python 3 scripts with a `run(ctx)` function. Choose SCALAR or SET
  input mode deliberately.
- Use `GROUP BY` as the parallelism unit (for example per SKU-store forecasts).
- Extra packages or models go into an SLC or BucketFS, not installed ad hoc.
- UDFs must NOT call external APIs. Ticket text must never leave the database.
- Every UDF needs a local test using `exasol-udf-mock-python`, plus at least
  one integration check against the real database.
- Put SQL in `/sql` as numbered, idempotent files (`01_schema.sql`, `02_...`).
- Use `CREATE CONNECTION` or `.env` for credentials. Never hardcode them.

## Tech stack
- Python 3.11, `pyexasol`, pandas, numpy, scikit-learn, pytest, ruff
- UI: Streamlit
- Optional: Exasol MCP Server for the natural-language question box

## Repo layout
```
/data_gen     seeded synthetic data generator
/sql          schema, views, scoring logic (numbered files)
/udfs         Exasol Python UDFs (one file per UDF)
/load         bulk loader scripts
/app          Streamlit app
/benchmarks   timing scripts and charts
/tests        pytest tests (UDF mock tests + data checks)
/docs         README assets, DATA.md, DEPLOY.md, RESULTS.md, pitch outline
```

## Environment notes
- My machine is **Windows**. Use PowerShell-compatible commands or cross-platform
  Python. Do not assume `sh`, `curl | sh` or Linux-only paths.
- The `exasol` launcher is installed manually and available on PATH.
  Cloud deployment is done by me. Never assume the `local` preset works.
- Provide a `Makefile` AND a `make.ps1` (or Python task runner) with targets:
  `setup`, `data`, `load`, `score`, `app`, `test`, `demo`.

## Code quality
- Files under 300 lines. Small, single-purpose functions with type hints.
- Run `ruff` and `pytest` before declaring any task done.
- Small commits with clear messages (for example `feat(udfs): add identity scorer`).
- Do not refactor unrelated code. Do not add dependencies without saying why.

## Module quality bars (report real numbers in `docs/RESULTS.md`)
- **Identity resolution:** report precision and recall vs ground truth. Favour
  precision, because wrong merges are worse than missed ones.
- **Stock-out forecast:** backtest on held-out days and beat a naive
  "same as last week" baseline. Show the comparison.
- **Return model:** report AUC and check for data leakage. The returned flag
  must never be a feature.
- **Churn:** show flagged customers churn more than unflagged, using the labels.
- **Action queue:** every rupee figure must be traceable to SQL and raw rows.
- Never invent metrics. If something is unmeasured, say so.

## UX principles
- Plain language, rupee formatting, no data-science jargon.
- Home page is the ranked Action Queue.
- Every number has a "show SQL" view so judges can see Exasol doing the work.

## Docs and reproducibility (judged)
- README: overview, architecture (mermaid), setup, usage, screenshots, results,
  limitations, and impact assumptions clearly labelled as estimates.
- `docs/DEPLOY.md`: exact install, stop (`exasol stop`) and destroy steps,
  cloud cost warning.
- A fresh clone must work by following the README only. Test this.

## Working style
- Plan first for each module, then implement in small steps.
- After finishing a task: run tests, then summarise in at most 5 lines
  (what changed, how to run it, what is untested, any open risks).
- If an error repeats twice, stop and explain what you tried instead of
  looping. Ask me for the missing information.
- If a requirement is ambiguous, state your assumption in one line and proceed.
- Priority if time runs short: One Customer layer plus ONE excellent risk
  module beats three half-working ones.

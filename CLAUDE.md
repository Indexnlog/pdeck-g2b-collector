# pdeck-g2b-collector

## Purpose
- Collect and monitor Korea G2B procurement data for pdeck-linked company intelligence workflows.
- Support durable ingestion with explicit troubleshooting and health-check procedures.

## Repo Map
- `collectors/`: collection logic.
- `utils/`: shared helper code.
- `data/`: collected or working datasets.
- `monitor_health.py`: health and reliability checks.
- `g2b_diagnostic_test.py`: diagnostics.
- `TROUBLESHOOTING.md` and related guides: operational references.

## Rules
- Treat this repo as production-adjacent ingestion infrastructure.
- Keep operational reliability docs in sync with code changes.
- Avoid mixing ad hoc debugging with canonical collector logic.
- Preserve health-check behavior when changing failure handling.

## Common Commands
```bash
python monitor_health.py
python g2b_diagnostic_test.py
run_collector.bat
```

## Workflow
- If error handling changes, update troubleshooting docs in the same change.
- Keep collector behavior, monitoring, and runbook guidance aligned.

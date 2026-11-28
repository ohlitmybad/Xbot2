# INDEX bot

## GitHub
Runs via `.github/workflows/post.yml` on `workflow_dispatch` (Apps Script `trigger.gs`) or push to `main`.

## Local
```bash
python run_local.py --runs 1
```

## Files
- `test_twi.py` — post runner
- `run_local.py` — local dry-run
- `metrics_config.json` / `prior_weights.json` — pools, excludes, hand dials
- `trigger.gs` — local-only Apps Script (not committed)

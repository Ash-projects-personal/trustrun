# CWE-bench v2 snapshot (TRUSTRUN-AuditAndRepair)

Local working state for the audit-and-repair eval target
(`trustrun/audit_repair`). No snapshot is present yet.

- Dataset: `collinear-ai/cwe-bench`, CWE-bench v2, 100 public tasks,
  Apache 2.0, GATED.
- Fetch: `HF_TOKEN=<token> python3 evals/cwe_bench/fetch_cwe_bench.py`
  (see the script docstring). The token must belong to an account
  that accepted the access conditions on the dataset page.
- Status 2026-11-16: fetch BLOCKED — no HF token is configured in
  this environment, and the Hub returns 401 on every task file
  (verified 2026-11-16 ~12:26 CST). The dataset README is public
  and was read in full; the task files are not. The module, its
  tests, and the fetch script are built and green; the 100 real
  tasks fold in once access is granted.
- Layout once fetched: `snapshot/` holds LICENSE, NOTICE, README.md,
  registry.json, manifest.json, and `tasks/<name>/` per task.
  The snapshot is local working state, not shipped content: never
  republish `solution/solve.sh` (dataset terms forbid it).

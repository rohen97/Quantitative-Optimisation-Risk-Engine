# Wolf Quant Autonomous Operations

Use the repository's measured, checkpointed execution paths for long-running work.

1. Work in phases: discover, isolate, implement, test, run, verify, publish.
2. Preserve observed data and existing user changes. Never replace missing evidence with synthetic data unless a test explicitly requests it.
3. Keep concurrency bounded. Avoid nested process pools, cap in-flight securities, and respect the DuckDB memory and thread settings.
4. Make provider ingestion idempotent and checkpoint successful atomic chunks before retrying. Treat quotas and entitlements as external evidence, not model success.
5. On a test failure, inspect the traceback, apply a scoped fix, and retry up to five times before recording a hard blocker.
6. A full research run is done only when required tests pass, no managed child process remains, reports are checksummed, presentation artifacts are rendered and inspected, and the execution report records any external limits.
7. Never commit Bloomberg observations, local databases, credentials, provider caches, or raw licensed payloads.

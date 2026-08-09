# Security Policy

## Credentials

- Store provider credentials in the ignored `.env` file or an external secret manager.
- Keep `.env.example` limited to variable names, safe defaults, and empty credential values.
- Never place API keys in source files, reports, logs, issue bodies, pull requests, or command examples.
- Redact credential-bearing query parameters from errors and observability output.

Any credential that has appeared in Git history must be rotated at the provider.
Deleting it from the latest revision does not invalidate older commits. Repository
history should only be rewritten after all affected collaborators coordinate the
force-push and replace local clones.

## Reporting A Vulnerability

Report vulnerabilities privately to the repository owner. Do not open a public
issue containing credentials, exploit details, portfolio data, or non-public
provider payloads.

## Operational Boundary

The project is research software. Production jobs default to dry-run controls,
and model governance approval does not authorize unattended order execution.

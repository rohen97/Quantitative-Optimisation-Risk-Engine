from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
from typing import Iterable


_CREDENTIAL_NAMES = {
    "ALPACA_API_KEY_ID",
    "ALPACA_API_SECRET_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "EODHD_API_KEY",
    "EODHD_API_TOKEN",
    "FINNHUB_API_KEY",
    "FRED_API_KEY",
    "ITICK_API_KEY",
    "ITICK_API_TOKEN",
    "ITICK_TOKEN",
    "TICKDB_API_KEY",
    "TICKDB_TOKEN",
    "BEAM_API_KEY",
    "NASDAQ_DATA_LINK_API_KEY",
    "OPENFIGI_API_KEY",
    "OPEN_FIGI_API_KEY",
}
_NAME_EXPRESSION = "|".join(
    sorted(
        (re.escape(name).replace("_", r"[\s_-]+") for name in _CREDENTIAL_NAMES),
        key=len,
        reverse=True,
    )
)
_ASSIGNMENT = re.compile(
    rf"(?i)(?P<name>{_NAME_EXPRESSION})\s*(?:=|:)\s*(?P<value>[^\s#;,]+)"
)
_SEARCH_TERMS = "ALPACA|ALPHA.VANTAGE|EODHD|FINNHUB|FRED|ITICK|TICKDB|BEAM|NASDAQ|OPENFIGI"
_PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "replace",
    "changeme",
    "your_",
    "your-",
    "dummy",
    "sample",
    "mock",
    "test",
)


@dataclass(frozen=True)
class CredentialFinding:
    credential_class: str
    path: str
    line_number: int
    commit: str | None


def _canonical_name(value: str) -> str:
    return re.sub(r"[\s-]+", "_", value.strip().upper())


def _is_placeholder(value: str) -> bool:
    clean = value.strip().strip("'\"")
    lower = clean.lower()
    if not clean or clean in {"''", '""'}:
        return True
    if clean.startswith(("${", "$env:", "%")) or clean.endswith("}"):
        return True
    if any(marker in lower for marker in _PLACEHOLDER_MARKERS):
        return True
    if set(clean) <= {"x", "X", "*", "-", "_", "."}:
        return True
    return False


def findings_from_line(
    text: str,
    *,
    path: str,
    line_number: int,
    commit: str | None = None,
) -> list[CredentialFinding]:
    findings: list[CredentialFinding] = []
    for match in _ASSIGNMENT.finditer(text):
        if _is_placeholder(match.group("value")):
            continue
        findings.append(
            CredentialFinding(
                credential_class=_canonical_name(match.group("name")),
                path=path,
                line_number=int(line_number),
                commit=commit,
            )
        )
    return findings


def _run_git(repository_root: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _parse_grep_lines(lines: Iterable[str], commit: str | None) -> list[CredentialFinding]:
    findings: list[CredentialFinding] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        if commit and line.startswith(f"{commit}:"):
            line = line[len(commit) + 1 :]
        parts = line.split(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            continue
        path, line_number, text = parts
        findings.extend(
            findings_from_line(
                text,
                path=path,
                line_number=int(line_number),
                commit=commit,
            )
        )
    return findings


def _scan_untracked_files(repository_root: Path) -> list[CredentialFinding]:
    result = _run_git(
        repository_root,
        ["ls-files", "--others", "--exclude-standard"],
    )
    if result.returncode != 0:
        raise RuntimeError("Unable to enumerate non-ignored untracked files.")

    findings: list[CredentialFinding] = []
    for relative_path in result.stdout.splitlines():
        candidate = (repository_root / relative_path).resolve()
        try:
            candidate.relative_to(repository_root)
        except ValueError:
            continue
        if not candidate.is_file():
            continue
        try:
            with candidate.open("rb") as raw:
                if b"\x00" in raw.read(4096):
                    continue
                raw.seek(0)
                for line_number, line in enumerate(raw, start=1):
                    text = line.decode("utf-8", errors="replace")
                    findings.extend(
                        findings_from_line(
                            text,
                            path=relative_path.replace("\\", "/"),
                            line_number=line_number,
                        )
                    )
        except OSError:
            continue
    return findings


def scan_git_credentials(repository_root: str | Path) -> dict[str, object]:
    root = Path(repository_root).resolve()
    revisions = _run_git(root, ["rev-list", "--all"])
    if revisions.returncode != 0:
        raise RuntimeError("Unable to enumerate Git history for credential audit.")
    commits = [line.strip() for line in revisions.stdout.splitlines() if line.strip()]

    historical: list[CredentialFinding] = []
    for commit in commits:
        result = _run_git(
            root,
            ["grep", "-I", "-n", "-i", "-E", _SEARCH_TERMS, commit, "--"],
        )
        if result.returncode not in {0, 1}:
            raise RuntimeError(f"Git history scan failed at commit {commit[:12]}.")
        historical.extend(_parse_grep_lines(result.stdout.splitlines(), commit))

    current_result = _run_git(
        root,
        ["grep", "-I", "-n", "-i", "-E", _SEARCH_TERMS, "--"],
    )
    if current_result.returncode not in {0, 1}:
        raise RuntimeError("Current-tree credential scan failed.")
    current = _parse_grep_lines(current_result.stdout.splitlines(), None)
    current.extend(_scan_untracked_files(root))

    def summary(findings: list[CredentialFinding]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for credential_class in sorted({item.credential_class for item in findings}):
            selected = [item for item in findings if item.credential_class == credential_class]
            rows.append(
                {
                    "credential_class": credential_class,
                    "occurrences": len(selected),
                    "affected_commits": len({item.commit for item in selected if item.commit}),
                    "paths": sorted({item.path for item in selected}),
                }
            )
        return rows

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scanner": "redacted_known_provider_assignment_audit_v2",
        "commits_scanned": len(commits),
        "current_tree_status": "PASS" if not current else "FAIL",
        "history_status": "PASS" if not historical else "REQUIRES_REMEDIATION",
        "current_tree_findings": summary(current),
        "historical_findings": summary(historical),
        "redaction_guarantee": "Credential values and value fingerprints are never written to this report.",
        "limitations": (
            "This targeted audit detects assignments for known provider credential classes. "
            "Provider-side revocation and a general-purpose secret scanner remain required."
        ),
    }


def write_credential_audit(report: dict[str, object], output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination

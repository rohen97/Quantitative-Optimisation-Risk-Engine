import json
import subprocess

from src.utils.credential_audit import findings_from_line, scan_git_credentials


def test_credential_audit_detects_value_without_retaining_it():
    findings = findings_from_line(
        "FRED_API_KEY" + "=" + "live-value-123",
        path="old.env",
        line_number=4,
        commit="abc123",
    )

    assert len(findings) == 1
    assert findings[0].credential_class == "FRED_API_KEY"
    assert "live-value-123" not in repr(findings[0])


def test_credential_audit_ignores_placeholders_and_environment_references():
    lines = (
        "OPENFIGI_API_KEY=",
        "BEAM_API_KEY=your_api_key",
        "NASDAQ_DATA_LINK_API_KEY=${NASDAQ_DATA_LINK_API_KEY}",
        "ITICK_TOKEN=xxxxxxxx",
    )

    assert not any(
        findings_from_line(text, path=".env.example", line_number=index)
        for index, text in enumerate(lines, start=1)
    )


def test_credential_audit_scans_nonignored_untracked_files(tmp_path):
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    value = "pending-secret-value"
    (tmp_path / "pending.env.txt").write_text(
        "OPENFIGI_API_KEY" + "=" + value + "\n",
        encoding="utf-8",
    )

    report = scan_git_credentials(tmp_path)

    assert report["current_tree_status"] == "FAIL"
    assert report["history_status"] == "PASS"
    assert report["current_tree_findings"] == [
        {
            "credential_class": "OPENFIGI_API_KEY",
            "occurrences": 1,
            "affected_commits": 0,
            "paths": ["pending.env.txt"],
        }
    ]
    assert value not in json.dumps(report)


def test_credential_audit_covers_openfigi_alias():
    findings = findings_from_line(
        "OPEN_FIGI_API_KEY" + "=" + "live-alias-value",
        path="local.env",
        line_number=1,
    )

    assert [item.credential_class for item in findings] == [
        "OPEN_FIGI_API_KEY"
    ]

from src.reporting.report_bundle import copy_to_latest, prepare_report_directory


def test_report_bundle_copies_latest_without_symlink(tmp_path):
    report_dir = prepare_report_directory(tmp_path / "ic", tmp_path / "latest", "run1")
    (report_dir / "x.txt").write_text("ok", encoding="utf-8")
    copy_to_latest(report_dir, tmp_path / "latest")
    assert (tmp_path / "latest" / "x.txt").read_text(encoding="utf-8") == "ok"

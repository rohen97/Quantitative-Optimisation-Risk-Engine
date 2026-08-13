import json

from src.validation.data_loader import _read_json


def test_read_json_accepts_windows_utf8_bom(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"artifact_version": 3}).encode())
    assert _read_json(path) == {"artifact_version": 3}

import sys

import main as cli


def test_cli_does_not_overwrite_source(tmp_path, monkeypatch, capsys):
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"keep original")
    monkeypatch.setattr(sys, "argv", ["main.py", str(source), "-o", str(source)])
    assert cli.main() == 1
    assert source.read_bytes() == b"keep original"
    assert "overwrite" in capsys.readouterr().err


def test_cli_rejects_output_inside_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", str(tmp_path), "-o", str(tmp_path / "report.xlsx")])
    assert cli.main() == 1


def test_cli_handles_corrupt_workbook(tmp_path, monkeypatch, capsys):
    source = tmp_path / "broken.xlsx"
    source.write_bytes(b"not an Excel workbook")
    monkeypatch.setattr(sys, "argv", ["main.py", str(source), "-o", str(tmp_path / "report.xlsx")])
    assert cli.main() == 1
    assert "ERROR:" in capsys.readouterr().err

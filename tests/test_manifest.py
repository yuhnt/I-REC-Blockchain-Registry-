from rec.config import ROOT
from rec.manifest import MILESTONES, digest


def test_digest_ignores_line_endings(tmp_path):
    lf, crlf = tmp_path / "lf.txt", tmp_path / "crlf.txt"
    lf.write_bytes(b"a: 1\nb: 2\n")
    crlf.write_bytes(b"a: 1\r\nb: 2\r\n")
    assert digest(lf) == digest(crlf)


def test_spec_milestone_files_exist():
    for rel in MILESTONES["spec-v1"]:
        assert (ROOT / rel).is_file(), rel


def test_glob_entries_expand():
    from rec.manifest import files
    assert "rec/generator/cli.py" in files("testset-v1")

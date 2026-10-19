from rec.config import ROOT
from rec.manifest import MILESTONES, digest


def test_digest_ignores_line_endings(tmp_path):
    lf, crlf = tmp_path / "lf.txt", tmp_path / "crlf.txt"
    lf.write_bytes(b"a: 1\nb: 2\n")
    crlf.write_bytes(b"a: 1\r\nb: 2\r\n")
    assert digest(lf) == digest(crlf)


def test_milestone_files_exist():
    for files in MILESTONES.values():
        for rel in files:
            assert (ROOT / rel).is_file(), rel

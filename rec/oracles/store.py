"""Kho file off-chain của chuỗi 15 phút, mỗi file đặt tên theo `data_root` (FLOW.md mục 2).

`store/<data_root hex>.json` = {oracle, cp, day, unit, slot_ends[], values[]}, giá trị thiếu là null.
Khi đọc, `data_root` được tính lại từ `values`; lệch thì file bị coi là đã bị sửa.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from rec.oracles.encoding import MISSING, data_root, to_ints
from rec.schema import OracleId

UNIT = {OracleId.O1: "Wh", OracleId.O2: "Wh", OracleId.O3: "Wh/m2", OracleId.O4: "Wh/m2"}


class TamperedFile(Exception):
    pass


class FileStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, root: bytes) -> Path:
        return self.root / f"{root.hex()}.json"

    def put(self, oracle: OracleId, cp_id: str, day: int, values: np.ndarray, slot_ends: list[str] | None = None
            ) -> bytes:
        ints = to_ints(values)
        root = data_root(values)
        doc = {"oracle": oracle.value, "cp": cp_id, "day": day, "unit": UNIT[oracle], "slot_ends": slot_ends or [],
               "values": [None if v == MISSING else v for v in ints]}
        self.path(root).write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        return root

    def put_json(self, doc: dict) -> bytes:
        """File phụ (ví dụ reason code của verdict); tên là keccak của nội dung."""
        from eth_utils import keccak
        raw = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        h = keccak(raw)
        (self.root / f"{h.hex()}.json").write_bytes(raw)
        return h

    def get(self, root: bytes) -> dict:
        """Đọc file và kiểm hash; sai thì `TamperedFile`."""
        doc = json.loads(self.path(root).read_text(encoding="utf-8"))
        if data_root(doc["values"]) != root:
            raise TamperedFile(root.hex())
        return doc

    def verify(self, root: bytes) -> bool:
        try:
            self.get(root)
            return True
        except (FileNotFoundError, TamperedFile, KeyError, ValueError):
            return False

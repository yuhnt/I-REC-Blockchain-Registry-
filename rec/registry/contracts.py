"""Thông tin chung về ba contract: vai và thứ tự tài khoản, artifact đã biên dịch, bảng mã lỗi.

Dùng chung cho backend chain (`chain_registry`, `testnet_registry`), lệnh deploy (`rec/deploy/`) và dashboard, để
không nơi nào phải đọc hàm nội bộ của nơi khác.
"""
from __future__ import annotations

import json
from pathlib import Path

from eth_utils import keccak

from rec.schema import RejectReason

# Thứ tự vai = chỉ số tài khoản trong mnemonic (Hardhat: tài khoản mở khóa của node; Sepolia: TESTNET_MNEMONIC).
ROLES = ["deployer", "issuerA", "issuerB", "O1", "O2", "O3", "O4", "verifier", "auditor", "codeManager", "plant",
         "buyer1", "buyer2", "outsider", "buyer3"]
REASONS = list(RejectReason)  # thứ tự khớp enum Reason của DecisionGate
NAMES = ("DeviceRegistry", "CertificateRegistry", "DecisionGate")


def contracts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "contracts"


def artifact(name: str) -> dict:
    """ABI và bytecode do `npx hardhat compile` ghi ra."""
    path = contracts_dir() / "artifacts" / "contracts" / f"{name}.sol" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def error_selectors(names=NAMES) -> dict[str, str]:
    """Selector 4 byte → tên custom error, để đọc lý do revert."""
    out = {}
    for name in names:
        for item in artifact(name)["abi"]:
            if item["type"] == "error":
                sig = f"{item['name']}(" + ",".join(i["type"] for i in item["inputs"]) + ")"
                out["0x" + keccak(text=sig)[:4].hex()] = item["name"]
    return out

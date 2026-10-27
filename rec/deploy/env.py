"""Đọc `contracts/.env` (không commit): SEPOLIA_RPC_URL, TESTNET_MNEMONIC, ETHERSCAN_API_KEY.

Chỉ trả giá trị cho nơi gọi; không in ra. URL RPC chứa API key, mnemonic suy ra mọi khóa của testnet.
"""
from __future__ import annotations

import re
from pathlib import Path

from rec.registry.contracts import contracts_dir


def load_env(path: Path | None = None) -> dict[str, str]:
    """KEY=VALUE mỗi dòng, bỏ dấu ngoặc kép bao ngoài; giống cách hardhat.config.ts đọc."""
    path = path or contracts_dir() / ".env"
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if m:
                out[m.group(1)] = re.sub(r"^(['\"])(.*)\1$", r"\2", m.group(2))
    return out

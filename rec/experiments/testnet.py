"""Chuẩn bị chạy trên testnet Sepolia, chỉ để trình diễn tra cứu công khai (thí nghiệm vẫn chạy trên Hardhat cục bộ).

Đọc `contracts/.env` (không commit): `SEPOLIA_RPC_URL`, `TESTNET_MNEMONIC`, tùy chọn `ETHERSCAN_API_KEY`.
Mnemonic sinh 15 tài khoản theo đúng thứ tự vai của `rec/registry/chain_registry.py` (`ROLES`).
Lệnh này **không bao giờ in** mnemonic, khóa riêng hay URL RPC (URL của Alchemy chứa API key).

Chạy: python -m rec.experiments.testnet addresses   → in địa chỉ, số dư Sepolia và vai nào cần ETH test
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from web3 import Web3

from rec.oracles.signer import hardhat_account
from rec.registry.chain_registry import ROLES, contracts_dir

# Vai gửi giao dịch on-chain nên cần ETH test; oracle và verifier chỉ ký off-chain.
NEEDS_GAS = {"deployer": "nhiều (deploy 3 contract, chia ETH cho các vai)", "issuerA": "vừa", "issuerB": "ít",
             "auditor": "ít", "codeManager": "ít", "plant": "vừa", "buyer1": "ít", "buyer2": "ít", "buyer3": "ít"}


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


def accounts(env: dict[str, str]) -> dict[str, str]:
    """Vai → địa chỉ (không trả khóa ra ngoài hàm)."""
    mnemonic = env.get("TESTNET_MNEMONIC", "").strip()
    if len(mnemonic.split()) not in (12, 15, 18, 21, 24):
        raise SystemExit("contracts/.env chưa có TESTNET_MNEMONIC hợp lệ (12 hoặc 24 từ, đặt trong dấu ngoặc kép)")
    return {role: hardhat_account(i, mnemonic).address for i, role in enumerate(ROLES)}


def cmd_addresses(env: dict[str, str]) -> int:
    addr = accounts(env)
    w3 = Web3(Web3.HTTPProvider(env["SEPOLIA_RPC_URL"])) if env.get("SEPOLIA_RPC_URL") else None
    if w3 is not None and w3.is_connected():
        chain_id = w3.eth.chain_id
        print(f"Kết nối RPC: chainId {chain_id}" + (" (Sepolia)" if chain_id == 11155111 else " – KHÔNG phải Sepolia!"))
    else:
        w3 = None
        print("Chưa kết nối được SEPOLIA_RPC_URL; chỉ in địa chỉ.")
    print(f"{'#':>2}  {'vai':<12} {'địa chỉ':<42}  {'số dư (ETH)':>12}  cần ETH test")
    for i, (role, a) in enumerate(addr.items()):
        bal = f"{w3.from_wei(w3.eth.get_balance(a), 'ether'):.5f}" if w3 else "—"
        print(f"{i:>2}  {role:<12} {a}  {bal:>12}  {NEEDS_GAS.get(role, 'không (chỉ ký off-chain)')}")
    print("\nXin ETH test từ faucet vào ví deployer (#0); các vai khác sẽ được chia từ deployer.")
    return 0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    env = load_env()
    if not argv or argv[0] == "addresses":
        return cmd_addresses(env)
    raise SystemExit(f"lệnh không xác định: {argv[0]}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

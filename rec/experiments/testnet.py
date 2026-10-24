"""Chuẩn bị chạy trên testnet Sepolia, chỉ để trình diễn tra cứu công khai (thí nghiệm vẫn chạy trên Hardhat cục bộ).

Đọc `contracts/.env` (không commit): `SEPOLIA_RPC_URL`, `TESTNET_MNEMONIC`, tùy chọn `ETHERSCAN_API_KEY`.
Mnemonic sinh 15 tài khoản theo đúng thứ tự vai của `rec/registry/chain_registry.py` (`ROLES`).
Lệnh này **không bao giờ in** mnemonic, khóa riêng hay URL RPC (URL của Alchemy chứa API key).

Các lệnh (chạy theo thứ tự; mọi lệnh gửi giao dịch đều tốn ETH test và ghi công khai lên Sepolia):
  python -m rec.experiments.testnet addresses     in địa chỉ, số dư và vai nào cần ETH test (không gửi gì)
  python -m rec.experiments.testnet fund          chia ETH từ deployer cho các vai cần gửi giao dịch
  python -m rec.experiments.testnet deploy        deploy 3 contract, ghi artifacts/testnet/deployment.json
  python -m rec.experiments.testnet verify        đăng mã nguồn lên Sepolia Etherscan (cần ETHERSCAN_API_KEY)
  python -m rec.experiments.testnet demo [--days 3]   nạp vài ngày dữ liệu demo (một lần cho mỗi lần deploy)
  python -m rec.experiments.testnet status        in địa chỉ contract và liên kết Etherscan
deploy, verify, demo tự ghi docs/TESTNET.md (chỉ thông tin công khai) để commit cho nhóm.
Sau đó: streamlit run dashboard/app.py, chọn chain "Sepolia" ở thanh bên.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from web3 import Web3

from rec import config
from rec.oracles.signer import hardhat_account
from rec.registry.chain_registry import ROLES, contracts_dir

EXPLORER = "https://sepolia.etherscan.io"
SEPOLIA_CHAIN_ID = 11155111
# Mức nạp cho các vai gửi giao dịch (ETH test), đủ cho demo vài ngày ở phí Sepolia thông thường.
FUND_ETH = {"issuerA": 0.015, "issuerB": 0.004, "auditor": 0.002, "codeManager": 0.003, "plant": 0.006,
            "buyer1": 0.002, "buyer2": 0.002, "buyer3": 0.002}

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


def dep_path() -> Path:
    return config.resolve_path("artifacts") / "testnet" / "deployment.json"


def _w3(env: dict[str, str]) -> Web3:
    if not env.get("SEPOLIA_RPC_URL"):
        raise SystemExit("contracts/.env chưa có SEPOLIA_RPC_URL")
    w3 = Web3(Web3.HTTPProvider(env["SEPOLIA_RPC_URL"], request_kwargs={"timeout": 60}))
    if w3.eth.chain_id != SEPOLIA_CHAIN_ID and env.get("REC_ALLOW_ANY_CHAIN") != "1":
        raise SystemExit(f"RPC không phải Sepolia (chainId {w3.eth.chain_id})")
    return w3


def cmd_fund(env: dict[str, str]) -> int:
    """Nạp mỗi vai lên mức FUND_ETH (chỉ gửi phần còn thiếu)."""
    w3 = _w3(env)
    mnemonic = env["TESTNET_MNEMONIC"]
    deployer = hardhat_account(0, mnemonic)
    plan = []
    for role, target in FUND_ETH.items():
        a = hardhat_account(ROLES.index(role), mnemonic).address
        missing = w3.to_wei(target, "ether") - w3.eth.get_balance(a)
        if missing > 0:
            plan.append((role, a, missing))
    need = sum(m for _, _, m in plan)
    have = w3.eth.get_balance(deployer.address)
    print(f"deployer có {w3.from_wei(have, 'ether'):.5f} ETH; cần chuyển {w3.from_wei(need, 'ether'):.5f} ETH cho "
          f"{len(plan)} vai")
    if need > have:
        raise SystemExit("deployer không đủ ETH: xin thêm từ faucet rồi chạy lại")
    nonce = w3.eth.get_transaction_count(deployer.address, "pending")
    fee = w3.eth.gas_price
    hashes = []
    for i, (role, a, value) in enumerate(plan):
        tx = {"to": a, "value": value, "gas": 21_000, "maxFeePerGas": 2 * fee, "maxPriorityFeePerGas": max(fee // 10, 1),
              "nonce": nonce + i, "chainId": w3.eth.chain_id, "type": 2}
        hashes.append((role, w3.eth.send_raw_transaction(deployer.sign_transaction(tx).raw_transaction)))
    for role, h in hashes:
        w3.eth.wait_for_transaction_receipt(h, timeout=600, poll_latency=2)
        print(f"  {role:<12} {EXPLORER}/tx/0x{bytes(h).hex()}")
    return 0


def _plant():
    from rec.experiments.runner import plant_from_config
    return plant_from_config(config.load("scenarios")["plant"])


def _jsonable(x):
    if isinstance(x, (bytes, bytearray)):
        return "0x" + bytes(x).hex()
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return x


def cmd_deploy(env: dict[str, str], argv: list[str]) -> int:
    from rec.experiments.demo import deployment_info
    from rec.registry.chain_registry import TestnetRegistry
    _w3(env)
    if dep_path().exists() and "--force" not in argv:
        raise SystemExit(f"đã có {dep_path()}; thêm --force để deploy bộ contract mới")
    print("deploy 3 contract lên Sepolia (mỗi giao dịch chờ khoảng 12–30 giây)…", flush=True)
    chain = TestnetRegistry(_plant(), env["SEPOLIA_RPC_URL"], env["TESTNET_MNEMONIC"])
    dep = {"network": "sepolia", "chain_id": SEPOLIA_CHAIN_ID, "explorer": EXPLORER, "from_block": chain.deploy_block,
           **deployment_info(chain), "deploy_args": {k: _jsonable(v) for k, v in chain.deploy_args.items()},
           "store": str(config.resolve_path("artifacts") / "store"), "held_requests": [],
           "deployed_at": date.today().isoformat()}
    dep_path().parent.mkdir(parents=True, exist_ok=True)
    _save(dep)
    return cmd_status(env)


def cmd_verify(env: dict[str, str]) -> int:
    if not env.get("ETHERSCAN_API_KEY"):
        raise SystemExit("contracts/.env chưa có ETHERSCAN_API_KEY")
    dep = json.loads(dep_path().read_text(encoding="utf-8"))
    for name, addr in dep["contracts"].items():
        args_file = dep_path().parent / f"args_{name}.js"
        args_file.write_text("module.exports = " + json.dumps(dep["deploy_args"][name]) + ";\n", encoding="utf-8")
        print(f"verify {name} …", flush=True)
        res = subprocess.run(f'npx hardhat verify --network sepolia --constructor-args "{args_file}" {addr}',
                             shell=True, cwd=contracts_dir(), capture_output=True, text=True)
        text = res.stdout + res.stderr
        print(text.strip()[-400:])
        dep.setdefault("verified", {})[name] = res.returncode == 0 or "already verified" in text.lower()
    _save(dep)
    return cmd_status(env)


def cmd_demo(env: dict[str, str], argv: list[str]) -> int:
    from rec.experiments.demo import populate
    from rec.registry.chain_registry import TestnetRegistry
    dep = json.loads(dep_path().read_text(encoding="utf-8"))
    if dep.get("demo_loaded") and "--force" not in argv:
        raise SystemExit("demo đã được nạp cho bộ contract này; deploy mới (deploy --force) nếu muốn nạp lại")
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 3
    _w3(env)
    chain = TestnetRegistry(_plant(), env["SEPOLIA_RPC_URL"], env["TESTNET_MNEMONIC"], deployment=dep)
    print(f"nạp {days} ngày dữ liệu demo lên Sepolia (khoảng {days * 15 + 30} giao dịch)…", flush=True)
    extra = populate(chain, n_days=days, lots=("M2-k1", "honest"))
    gas = sum(g for _, g in chain.gas_log)
    dep.update(extra, demo_loaded=True, demo_summary={"days": days, "transactions": len(chain.gas_log), "gas": gas,
                                                      "loaded_at": date.today().isoformat()})
    _save(dep)
    print("tổng gas:", gas, "trên", len(chain.gas_log), "giao dịch")
    return cmd_status(env)


def write_notes(dep: dict) -> Path:
    """Ghi docs/TESTNET.md từ deployment.json: chỉ thông tin công khai (địa chỉ, block, tx, liên kết Etherscan).

    Không ghi mnemonic, khóa riêng, URL RPC hay API key.
    """
    ex = dep.get("explorer", EXPLORER)
    c = dep["contracts"]
    lines = ["# Trình diễn trên testnet Sepolia", "",
             "File này do `python -m rec.experiments.testnet` tự ghi sau mỗi lần `deploy`, `verify`, `demo`. "
             "Chỉ chứa thông tin công khai trên chain. Thí nghiệm E1–E3 vẫn chạy trên Hardhat cục bộ "
             "(RESULTS.md); Sepolia chỉ để tra cứu công khai.", "",
             "## Contract", "",
             f"Deploy ngày {dep.get('deployed_at', '—')}, từ block {dep['from_block']} (chainId {dep.get('chain_id')}).",
             "", "| Contract | Địa chỉ | Mã nguồn |", "|---|---|---|"]
    verified = dep.get("verified", {})
    for name, addr in c.items():
        mark = "đã verify" if verified.get(name) else "chưa verify"
        lines.append(f"| {name} | [`{addr}`]({ex}/address/{addr}) | {mark} |")
    lines += ["", f"Chứng chỉ ERC-1155 (đơn vị Wh): [{ex}/token/{c['CertificateRegistry']}]"
                  f"({ex}/token/{c['CertificateRegistry']}). Tra một chứng chỉ: thêm `?a=<tokenId>`; tokenId = "
                  "keccak256(abi.encode(deviceId, day)), có sẵn ở dashboard (tab Tra chứng chỉ).", ""]
    if dep.get("demo_loaded"):
        d = dep.get("demo_summary", {})
        lines += ["## Dữ liệu demo", "",
                  f"Nạp ngày {d.get('loaded_at', '—')}: {d.get('days', '—')} ngày đầu của dòng hợp lệ (seed 101, "
                  "cấu hình Proposed), cùng D1 và D4a bị REJECT, các lô chờ Production Auditor, và một lần tạm khóa "
                  "và rút của Code Manager.", "",
                  f"- Giao dịch: {d.get('transactions', '—')}, tổng gas {d.get('gas', 0):,}",
                  f"- Yêu cầu đang bị giữ chờ auditor: {len(dep.get('held_requests', []))}", ""]
    lines += ["## Địa chỉ các vai", "",
              "Suy ra từ mnemonic riêng của nhóm (không công bố). Oracle và verifier chỉ ký off-chain.", "",
              "| Vai | Địa chỉ |", "|---|---|"]
    lines += [f"| {role} | [`{a}`]({ex}/address/{a}) |" for role, a in dep["roles"].items()]
    lines += ["", "## Chạy lại", "", "Xem README, mục trình diễn trên testnet Sepolia. Mở dashboard và chọn chain "
              "\"Sepolia (testnet)\" ở thanh bên.", ""]
    out = config.ROOT / "docs" / "TESTNET.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return out


def _save(dep: dict) -> None:
    dep_path().write_text(json.dumps(dep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("đã cập nhật", write_notes(dep).relative_to(config.ROOT))


def cmd_status(env: dict[str, str]) -> int:
    if not dep_path().exists():
        raise SystemExit("chưa deploy (python -m rec.experiments.testnet deploy)")
    dep = json.loads(dep_path().read_text(encoding="utf-8"))
    print(f"Sepolia, từ block {dep['from_block']}:")
    for name, addr in dep["contracts"].items():
        print(f"  {name:<20} {EXPLORER}/address/{addr}")
    print(f"  chứng chỉ (ERC-1155)  {EXPLORER}/token/{dep['contracts']['CertificateRegistry']}")
    return 0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    env = load_env()
    cmd = argv[0] if argv else "addresses"
    if cmd == "addresses":
        return cmd_addresses(env)
    if cmd == "status":
        return cmd_status(env)
    accounts(env)  # kiểm mnemonic trước khi gửi gì
    if cmd == "fund":
        return cmd_fund(env)
    if cmd == "deploy":
        return cmd_deploy(env, argv)
    if cmd == "verify":
        return cmd_verify(env)
    if cmd == "demo":
        return cmd_demo(env, argv)
    raise SystemExit(f"lệnh không xác định: {cmd}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

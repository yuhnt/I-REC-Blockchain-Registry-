"""Backend chain: gọi ba contract trên Hardhat Network qua web3.py (FLOW.md mục 9–11).

- `HardhatNode` khởi động `npx hardhat node` với ngày bắt đầu trước dòng sự kiện, để đặt timestamp của block
  theo đồng hồ mô phỏng (`evm_setNextBlockTimestamp`).
- `ChainRegistry` deploy một lần, chụp snapshot, rồi `reset()` về snapshot trước mỗi dòng sự kiện.
Khóa oracle và verifier là tài khoản kiểm thử công khai của Hardhat; các vai khác dùng tài khoản đã mở khóa của node.
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import time
from pathlib import Path

from eth_utils import keccak
from web3 import Web3

from rec import config
from rec.oracles.signer import Signer, b32, hardhat_account, lot_key, report_struct, reports_hash, struct_hash, token_id
from rec.registry.base import LotEvidence, Outcome, Plant, Registry
from rec.schema import RejectReason

ROLES = ["deployer", "issuerA", "issuerB", "O1", "O2", "O3", "O4", "verifier", "auditor", "codeManager", "plant",
         "buyer1", "buyer2", "outsider", "buyer3"]
REASONS = list(RejectReason)  # thứ tự khớp enum Reason của DecisionGate
GAS = 3_000_000


class _Receipt:
    __slots__ = ("gasUsed", "transactionHash", "logs")

    def __init__(self, gas: int, tx_hash: str, logs: list):
        self.gasUsed, self.transactionHash, self.logs = gas, tx_hash, logs


def contracts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "contracts"


def _artifact(name: str) -> dict:
    path = contracts_dir() / "artifacts" / "contracts" / f"{name}.sol" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class HardhatNode:
    """Tiến trình `npx hardhat node` chạy nền; dừng khi `close()`."""

    def __init__(self, port: int = 8545, initial_date: str = "2021-12-01T00:00:00Z", interval_ms: int | None = None):
        self.port = port
        env = dict(os.environ, REC_INITIAL_DATE=initial_date)
        if interval_ms:
            env["REC_INTERVAL_MS"] = str(interval_ms)
        log = open(config.resolve_path("artifacts") / f"hardhat_node_{port}.log", "w", encoding="utf-8")
        self.proc = subprocess.Popen(f"npx hardhat node --port {port}", cwd=contracts_dir(), env=env, stdout=log,
                                     stderr=subprocess.STDOUT, shell=True)
        self.url = f"http://127.0.0.1:{port}"
        w3 = Web3(Web3.HTTPProvider(self.url))
        for _ in range(120):
            try:
                if w3.is_connected():
                    return
            except Exception:  # noqa: BLE001 – node chưa lên
                pass
            time.sleep(0.5)
        raise RuntimeError("Hardhat node không khởi động được (xem artifacts/hardhat_node.log)")

    def close(self) -> None:
        if os.name == "nt":
            subprocess.run(f"taskkill /F /T /PID {self.proc.pid}", shell=True, capture_output=True)
        else:
            self.proc.terminate()


class ChainRegistry(Registry):
    name = "chain"

    def __init__(self, plant: Plant, url: str, interval_mining: bool = False):
        self.plant = plant
        self.interval_mining = interval_mining  # E3: block mỗi 2 giây, không đặt timestamp theo đồng hồ mô phỏng
        self.arrival_jitter_s = 0.0
        self._rng = random.Random(0)
        self.w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 60}))
        accts = self.w3.eth.accounts
        self.addr = {role: Web3.to_checksum_address(accts[i]) for i, role in enumerate(ROLES)}
        self.keys = {role: hardhat_account(ROLES.index(role)) for role in ("O1", "O2", "O3", "O4", "verifier")}
        self._deploy()
        self.signer = Signer(self.gate.address)
        self._errors = self._error_selectors()
        self._topics = {name: keccak(text=sig) for name, sig in (
            ("Issued", "Issued(bytes32,uint256,bytes32,uint32,uint64,address)"),
            ("IssueRejected", "IssueRejected(bytes32,bytes32,uint32,uint8)"),
            ("IssueHeld", "IssueHeld(bytes32,bytes32)"),
            ("O1Conflict", "O1Conflict(bytes32,uint64,uint64)"))}
        self._snapshot = self._rpc("evm_snapshot")
        self.gas_log: list[tuple[str, int]] = []
        self.lat_log: list[tuple[str, float]] = []

    # ---------------------------------------------------------------- hạ tầng

    def _rpc(self, method: str, *params):
        resp = self.w3.provider.make_request(method, list(params))
        if "error" in resp:
            raise RuntimeError(resp["error"])
        return resp["result"]

    def _contract(self, name: str, address=None, args=()):
        art = _artifact(name)
        if address is not None:
            return self.w3.eth.contract(address=address, abi=art["abi"])
        factory = self.w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
        tx = factory.constructor(*args).transact({"from": self.addr["deployer"], "gas": 10_000_000})
        rcpt = self.w3.eth.wait_for_transaction_receipt(tx, poll_latency=0.05)
        return self.w3.eth.contract(address=rcpt.contractAddress, abi=art["abi"])

    def _deploy(self) -> None:
        cps = list(self.plant.cp_capacity_w)
        self.devices = self._contract("DeviceRegistry", args=(
            [self.addr[i] for i in self.plant.issuers], [b32(c) for c in cps], [self.plant.cp_capacity_w[c] for c in cps]))
        self.certs = self._contract("CertificateRegistry", args=(self.addr["codeManager"],))
        self.gate = self._contract("DecisionGate", args=(
            self.devices.address, self.certs.address, self.addr["auditor"], [b32(c) for c in cps],
            [self.addr[self.plant.holder_of[c]] for c in cps],
            [[self.addr[o] for o in ("O1", "O2", "O3", "O4")] for _ in cps], [self.addr["verifier"]]))
        tx = self.certs.functions.setGate(self.gate.address).transact({"from": self.addr["deployer"], "gas": GAS})
        self.w3.eth.wait_for_transaction_receipt(tx, poll_latency=0.05)

    def _error_selectors(self) -> dict[str, str]:
        out = {}
        for name in ("DeviceRegistry", "CertificateRegistry", "DecisionGate"):
            for item in _artifact(name)["abi"]:
                if item["type"] == "error":
                    sig = f"{item['name']}(" + ",".join(i["type"] for i in item["inputs"]) + ")"
                    out["0x" + keccak(text=sig)[:4].hex()] = item["name"]
        return out

    def checkpoint(self) -> None:
        """Lấy trạng thái hiện tại (ví dụ sau khi đăng ký thiết bị) làm điểm quay về của `reset()`."""
        self._snapshot = self._rpc("evm_snapshot")

    def reset(self) -> None:
        """Quay về điểm đã chụp (mặc định ngay sau deploy; dùng trước mỗi dòng sự kiện)."""
        self._rpc("evm_revert", self._snapshot)
        self._snapshot = self._rpc("evm_snapshot")
        self._last_t = 0

    def _at(self, t: int) -> None:
        if t > getattr(self, "_last_t", 0):
            try:
                self._rpc("evm_setNextBlockTimestamp", hex(t))
            except RuntimeError:
                pass  # đồng hồ chain đã đi trước (giao dịch cùng giây); giữ nguyên
            self._last_t = t

    def _send(self, fn, role: str, t: int, op: str):
        """Gửi giao dịch bằng RPC thô (không qua bước điền mặc định của web3, vốn hỏi phí và chainId mỗi lần).

        Trả (receipt, None), hoặc (None, tên lỗi) khi contract revert.
        """
        if not self.interval_mining:
            self._at(t)
        tx = {"from": self.addr[role], "to": fn.address, "data": fn._encode_transaction_data(), "gas": hex(GAS),
              "gasPrice": "0x0"}
        if self.arrival_jitter_s:  # E3: giao dịch đến vào thời điểm ngẫu nhiên so với nhịp đào block
            time.sleep(self._rng.uniform(0, self.arrival_jitter_s))
        t_send = time.perf_counter()
        resp = self.w3.provider.make_request("eth_sendTransaction", [tx])
        if "error" in resp:
            return None, self._decode_error(resp["error"])
        rcpt = None
        while rcpt is None:  # automine: có ngay; đào theo khoảng thời gian: chờ block kế tiếp
            rcpt = self.w3.provider.make_request("eth_getTransactionReceipt", [resp["result"]])["result"]
            if rcpt is None:
                time.sleep(0.02)
        self.lat_log.append((op, time.perf_counter() - t_send))
        if rcpt["status"] == "0x0":
            return None, "Revert"
        gas = int(rcpt["gasUsed"], 16)
        self.gas_log.append((op, gas))
        return _Receipt(gas, rcpt["transactionHash"], rcpt["logs"]), None

    def _decode_error(self, err) -> str:
        text = json.dumps(err) if isinstance(err, dict) else str(err)
        m = re.search(r"custom error '([A-Za-z0-9_]+)\(", text)
        if m:
            return m.group(1)
        for sel in re.findall(r"0x[0-9a-fA-F]{8}", text):
            if sel.lower() in self._errors:
                return self._errors[sel.lower()]
        return "Revert"

    def _logs(self, rcpt, name: str) -> list[bytes]:
        """Phần data của các log có topic0 là event `name`."""
        topic = "0x" + self._topics[name].hex()
        return [bytes.fromhex(lg["data"][2:]) for lg in rcpt.logs if lg["topics"] and lg["topics"][0] == topic]

    # ---------------------------------------------------------------- Registry

    def register_device(self, dev, t):
        fn = self.devices.functions.registerDevice(b32(dev.device_id), b32(dev.cp_id), dev.ac_capacity_w,
                                                   dev.effective_day, dev.is_group,
                                                   dev.member_count if dev.is_group else 1)
        rcpt, err = self._send(fn, dev.issuer, t, "register")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed, tx=rcpt.transactionHash)

    def transfer_registration(self, rt, t):
        fn = self.devices.functions.transferRegistration(b32(rt.device_id), self.addr[rt.to_issuer], rt.effective_day)
        rcpt, err = self._send(fn, rt.from_issuer, t, "transfer_registration")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed)

    def close_registration(self, dr, t):
        fn = self.devices.functions.closeRegistration(b32(dr.device_id), dr.effective_day)
        rcpt, err = self._send(fn, dr.issuer, t, "close_registration")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed)

    def evidence_args(self, ev: LotEvidence):
        structs = [report_struct(r) for r in ev.reports]
        sigs = [b"" if s["oracle"] == 0 else self.signer.sign(self.keys[f"O{i + 1}"], "OracleReport", s)
                for i, s in enumerate(structs)]
        verdict = {"lotKey": lot_key(ev.cp_id, ev.day), "flags": ev.flags, "ceilingWh": ev.ceiling_wh,
                   "sunSlots": ev.sun_slots, "reportsHash": reports_hash(structs), "modelHash": ev.model_hash,
                   "reasonsHash": ev.reasons_hash}
        vsig = self.signer.sign(self.keys["verifier"], "Verdict", verdict)
        to_tuple = lambda s, fields: tuple(s[n] for n in fields)
        rep = [to_tuple(s, ["oracle", "cpId", "day", "valueDay", "maxSlot", "slotsPresent", "dataRoot"]) for s in structs]
        ver = to_tuple(verdict, ["lotKey", "flags", "ceilingWh", "sunSlots", "reportsHash", "modelHash", "reasonsHash"])
        return rep, sigs, ver, vsig

    def submit_lot_evidence(self, ev, issuer, t):
        rep, sigs, ver, vsig = self.evidence_args(ev)
        rcpt, err = self._send(self.gate.functions.submitLotEvidence(rep, sigs, ver, vsig), issuer, t, "evidence")
        if err:
            return Outcome("revert", err)
        if self._logs(rcpt, "O1Conflict"):
            return Outcome("reject", "O1Conflict", gas=rcpt.gasUsed)
        return Outcome("ok", gas=rcpt.gasUsed)

    def resolve_review(self, cp_id, day, approve, t):
        fn = self.gate.functions.resolveReview(lot_key(cp_id, day), approve, b"\0" * 32)
        rcpt, err = self._send(fn, "auditor", t, "resolve_review")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed)

    def issue(self, req, t):
        fn = self.gate.functions.issue(b32(req.req_id[:31]), b32(req.device_id), req.day_start, list(req.wh_per_day))
        rcpt, err = self._send(fn, req.issuer, t, "issue")
        if err:
            return Outcome("revert", err)
        if (rej := self._logs(rcpt, "IssueRejected")):
            reason = REASONS[int.from_bytes(rej[0][-32:], "big")]
            return Outcome("reject", reason.value, gas=rcpt.gasUsed, tx=rcpt.transactionHash)
        if self._logs(rcpt, "IssueHeld"):
            return Outcome("held", gas=rcpt.gasUsed)
        minted = []
        for data in self._logs(rcpt, "Issued"):
            day, wh = int.from_bytes(data[0:32], "big"), int.from_bytes(data[32:64], "big")
            minted.append((req.device_id, day, wh))
        return Outcome("mint", minted=tuple(minted), gas=rcpt.gasUsed, tx=rcpt.transactionHash)

    def transfer(self, tr, t):
        fn = self.certs.functions.safeTransferFrom(self.addr[tr.sender], self.addr[tr.recipient],
                                                   token_id(tr.device_id, tr.day), tr.wh, b"")
        rcpt, err = self._send(fn, tr.sender, t, "transfer")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed)

    def retire(self, rt, t):
        fn = self.certs.functions.retire(token_id(rt.device_id, rt.day), rt.wh, rt.beneficiary, rt.purpose,
                                         rt.consumption_location, rt.reporting_period)
        rcpt, err = self._send(fn, rt.holder, t, "retire")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed)

    def suspend(self, device_id, day, active, reason, t):
        fn = self.certs.functions.suspend(token_id(device_id, day), active, reason)
        rcpt, err = self._send(fn, "codeManager", t, "suspend")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed)

    def withdraw(self, device_id, day, holder, wh, reason, t):
        fn = self.certs.functions.withdraw(token_id(device_id, day), self.addr[holder], wh, reason)
        rcpt, err = self._send(fn, "codeManager", t, "withdraw")
        return Outcome("revert", err) if err else Outcome("ok", gas=rcpt.gasUsed)

    def operator_edit(self, edit, t):
        """Contract không có hàm sửa, xóa hay phát hành lại. Thao tác gần nhất issuer thử được là gọi `withdraw`
        của Code Manager; nó luôn revert. Phát hành lại cùng (thiết bị, ngày) qua gate thì bị khóa ① chặn."""
        fn = self.certs.functions.withdraw(0, self.addr["plant"], 1, "insider")
        _, err = self._send(fn, edit.issuer, t, "operator_edit")
        return Outcome("revert", err or "NoAdminFunction")

    # tiện ích cho test parity và E3
    def lot_status(self, cp_id: str, day: int) -> int:
        return self.gate.functions.lotState(lot_key(cp_id, day)).call()[4]

    def struct_hash_onchain(self, ev: LotEvidence) -> tuple[bytes, bytes]:
        s = report_struct(ev.reports[0])
        rep = tuple(s[n] for n in ["oracle", "cpId", "day", "valueDay", "maxSlot", "slotsPresent", "dataRoot"])
        return bytes(self.gate.functions.reportHash(rep).call()), struct_hash("OracleReport", s)

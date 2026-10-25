"""Bốn oracle O1–O4 như bốn nút độc lập (FLOW.md mục 1–3).

Mỗi `OracleNode` có:
- **nguồn dữ liệu riêng** (O1 công tơ, O2 tổng 24 inverter, O3 bức xạ và nhiệt độ tại chỗ, O4 bức xạ vệ tinh NSRDB);
- **khóa ký riêng** (chỉ nút đó giữ); contract chỉ nhận báo cáo của oracle i nếu chữ ký khớp địa chỉ trong
  allowlist của (CP, oracle i), nên nút này không ký thay nút khác được;
- **quyền ghi riêng** vào kho file: chuỗi 15 phút lưu theo `data_root` của chính báo cáo.

Nút làm ba việc: dựng báo cáo ngày từ chuỗi 15 phút, lưu chuỗi vào kho, ký EIP-712. Không nút nào gửi giao dịch:
issuer gom 4 báo cáo đã ký vào `submitLotEvidence`.

Ở chế độ R1 khóa O1 thuộc điện lực; ở R2 khóa O1–O3 thuộc chủ dự án. O4 luôn thuộc issuer. Thí nghiệm mô hình hóa
điều này bằng việc ai giữ khóa nào; code của nút giống nhau.

Chạy thử một nút (in báo cáo đã ký, địa chỉ ký và kiểm chữ ký):
    python -m rec.oracles.node --oracle O2 --day 18993
"""
from __future__ import annotations

import dataclasses
import json
import sys
from dataclasses import dataclass

import numpy as np
from eth_account import Account
from eth_account.messages import encode_typed_data

from rec.generator.common import report
from rec.oracles.signer import HARDHAT_MNEMONIC, REPORT_FIELDS, Signer, hardhat_account, report_struct
from rec.oracles.store import FileStore
from rec.schema import OracleId, OracleReport

# Chỉ số tài khoản của mỗi oracle trong mnemonic, theo thứ tự vai của rec/registry/chain_registry.py (ROLES).
ACCOUNT_INDEX = {OracleId.O1: 3, OracleId.O2: 4, OracleId.O3: 5, OracleId.O4: 6}
SOURCE = {OracleId.O1: "Công tơ tại điểm đấu nối (PVDAQ, kênh meter), Wh",
          OracleId.O2: "Tổng 24 inverter, mỗi inverter đếm một lần (PVDAQ), Wh",
          OracleId.O3: "Bức xạ POA và nhiệt độ tại chỗ (PVDAQ), Wh/m²",
          OracleId.O4: "Bức xạ POA từ vệ tinh NSRDB, Wh/m²"}


@dataclass
class OracleNode:
    oracle: OracleId
    cp_id: str
    account: object  # LocalAccount; khóa riêng không rời khỏi nút
    signer: Signer
    store: FileStore | None = None

    @property
    def address(self) -> str:
        return self.account.address

    @property
    def source(self) -> str:
        return SOURCE[self.oracle]

    def sign(self, rep: OracleReport) -> OracleReport:
        """Ký một báo cáo của chính oracle này; từ chối ký báo cáo mang mã oracle khác."""
        if rep.oracle is not self.oracle:
            raise ValueError(f"nút {self.oracle.value} không ký báo cáo của {rep.oracle.value}")
        sig = self.signer.sign(self.account, "OracleReport", report_struct(rep))
        return dataclasses.replace(rep, signature=sig)

    def observe(self, day: int, values: np.ndarray, sun: np.ndarray, slot_ends: list[str] | None = None
                ) -> OracleReport:
        """Từ chuỗi 15 phút của ngày: dựng báo cáo, lưu chuỗi vào kho theo data_root, ký."""
        rep = report(self.oracle, self.cp_id, day, values, sun)
        if self.store is not None:
            root = self.store.put(self.oracle, self.cp_id, day, values, slot_ends)
            assert root == rep.data_root
        return self.sign(rep)


def oracle_nodes(cp_id: str, gate_address: str, chain_id: int, mnemonic: str = HARDHAT_MNEMONIC,
                 store: FileStore | None = None) -> dict[OracleId, OracleNode]:
    """Bốn nút O1–O4, mỗi nút một khóa suy ra từ mnemonic theo chỉ số riêng."""
    signer = Signer(gate_address, chain_id)
    return {o: OracleNode(o, cp_id, hardhat_account(i, mnemonic), signer, store) for o, i in ACCOUNT_INDEX.items()}


def recover_signer(rep: OracleReport, gate_address: str, chain_id: int) -> str:
    """Địa chỉ đã ký báo cáo (như contract làm với ECDSA.recover trên hash EIP-712)."""
    typed = {"types": {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                                        {"name": "chainId", "type": "uint256"},
                                        {"name": "verifyingContract", "type": "address"}],
                       "OracleReport": [{"name": n, "type": t} for n, t in REPORT_FIELDS]},
             "primaryType": "OracleReport",
             "domain": {"name": "REC-A5", "version": "1", "chainId": chain_id, "verifyingContract": gate_address},
             "message": report_struct(rep)}
    return Account.recover_message(encode_typed_data(full_message=typed), signature=rep.signature)


def main(argv: list[str]) -> int:
    """Chạy riêng một nút oracle trên dữ liệu của một ngày và in báo cáo đã ký."""
    sys.stdout.reconfigure(encoding="utf-8")
    import pandas as pd

    from rec import config
    from rec.generator.common import load_days

    oracle = OracleId(argv[argv.index("--oracle") + 1] if "--oracle" in argv else "O1")
    artifacts = config.resolve_path("artifacts")
    _, data = load_days()
    day = int(argv[argv.index("--day") + 1]) if "--day" in argv else min(data)
    dep_path = artifacts / "demo" / "deployment.json"
    gate, chain_id = ("0x" + "0" * 40, 31337)
    if dep_path.exists():
        gate = json.loads(dep_path.read_text(encoding="utf-8"))["contracts"]["DecisionGate"]
    slots = pd.read_parquet(artifacts / "slots.parquet")
    slot_ends = [t.isoformat() for t in slots[slots["day"] == day].index]
    node = oracle_nodes("CP-1", gate, chain_id, store=FileStore(artifacts / "store"))[oracle]
    dd = data[day]
    rep = node.observe(day, dd.series[oracle], dd.sun, slot_ends)
    print(json.dumps({"oracle": oracle.value, "nguồn": node.source, "địa chỉ ký": node.address,
                      "ngày": day, "valueDay": rep.wh_day, "maxSlot": rep.max_slot_wh,
                      "slotsPresent": rep.slots_present, "dataRoot": "0x" + rep.data_root.hex(),
                      "chữ ký": "0x" + rep.signature.hex(),
                      "kiểm chữ ký": recover_signer(rep, gate, chain_id) == node.address,
                      "file trong kho": str(node.store.path(rep.data_root))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

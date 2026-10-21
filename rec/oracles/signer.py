"""Ký báo cáo oracle và verdict theo EIP-712, khớp `DecisionGate` (FLOW.md mục 3).

Domain: name = "REC-A5", version = "1", chainId = 31337, verifyingContract = địa chỉ DecisionGate.
Khóa ký của thí nghiệm là các tài khoản kiểm thử công khai của Hardhat (mnemonic mặc định), không phải khóa thật.
"""
from __future__ import annotations

from dataclasses import dataclass

from eth_abi import encode as abi_encode
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak

from rec.schema import OracleId, OracleReport

HARDHAT_MNEMONIC = "test test test test test test test test test test test junk"
ORACLE_INDEX = {OracleId.O1: 1, OracleId.O2: 2, OracleId.O3: 3, OracleId.O4: 4}

REPORT_FIELDS = [("oracle", "uint8"), ("cpId", "bytes32"), ("day", "uint32"), ("valueDay", "uint64"),
                 ("maxSlot", "uint64"), ("slotsPresent", "uint16"), ("dataRoot", "bytes32")]
VERDICT_FIELDS = [("lotKey", "bytes32"), ("flags", "uint8"), ("ceilingWh", "uint64"), ("sunSlots", "uint16"),
                  ("reportsHash", "bytes32"), ("modelHash", "bytes32"), ("reasonsHash", "bytes32")]
_TYPE_STR = {name: f"{name}(" + ",".join(f"{t} {n}" for n, t in fields) + ")"
             for name, fields in (("OracleReport", REPORT_FIELDS), ("Verdict", VERDICT_FIELDS))}
REPORT_TYPEHASH = keccak(text=_TYPE_STR["OracleReport"])
VERDICT_TYPEHASH = keccak(text=_TYPE_STR["Verdict"])

Account.enable_unaudited_hdwallet_features()


def hardhat_account(index: int):
    return Account.from_mnemonic(HARDHAT_MNEMONIC, account_path=f"m/44'/60'/0'/0/{index}")


def b32(s: str) -> bytes:
    """Mã ASCII ≤ 31 ký tự → bytes32 đệm 0 bên phải (như ethers.encodeBytes32String)."""
    raw = s.encode("ascii")
    if len(raw) > 31:
        raise ValueError(f"mã quá dài cho bytes32: {s}")
    return raw.ljust(32, b"\0")


def lot_key(cp_id: str, day: int) -> bytes:
    return keccak(abi_encode(["bytes32", "uint32"], [b32(cp_id), day]))


def token_id(device_id: str, day: int) -> int:
    return int.from_bytes(keccak(abi_encode(["bytes32", "uint32"], [b32(device_id), day])), "big")


def report_struct(r: OracleReport | None) -> dict:
    """Struct `OracleReport` của contract; báo cáo thiếu là oracle = 0."""
    if r is None:
        return {"oracle": 0, "cpId": b"\0" * 32, "day": 0, "valueDay": 0, "maxSlot": 0, "slotsPresent": 0,
                "dataRoot": b"\0" * 32}
    return {"oracle": ORACLE_INDEX[r.oracle], "cpId": b32(r.subject), "day": r.day, "valueDay": r.wh_day,
            "maxSlot": r.max_slot_wh, "slotsPresent": r.slots_present, "dataRoot": r.data_root or b"\0" * 32}


def struct_hash(name: str, msg: dict) -> bytes:
    fields = REPORT_FIELDS if name == "OracleReport" else VERDICT_FIELDS
    typehash = REPORT_TYPEHASH if name == "OracleReport" else VERDICT_TYPEHASH
    return keccak(abi_encode(["bytes32"] + [t for _, t in fields], [typehash] + [msg[n] for n, _ in fields]))


def reports_hash(structs: list[dict]) -> bytes:
    hashes = [b"\0" * 32 if s["oracle"] == 0 else struct_hash("OracleReport", s) for s in structs]
    return keccak(abi_encode(["bytes32[4]"], [hashes]))


@dataclass
class Signer:
    gate_address: str
    chain_id: int = 31337

    def _domain(self) -> dict:
        return {"name": "REC-A5", "version": "1", "chainId": self.chain_id, "verifyingContract": self.gate_address}

    def sign(self, account, name: str, msg: dict) -> bytes:
        fields = REPORT_FIELDS if name == "OracleReport" else VERDICT_FIELDS
        typed = {"types": {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                                            {"name": "chainId", "type": "uint256"},
                                            {"name": "verifyingContract", "type": "address"}],
                           name: [{"name": n, "type": t} for n, t in fields]},
                 "primaryType": name, "domain": self._domain(), "message": msg}
        return bytes(account.sign_message(encode_typed_data(full_message=typed)).signature)

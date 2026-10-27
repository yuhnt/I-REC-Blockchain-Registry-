"""Lineage completeness: dựng lại chuỗi của từng chứng chỉ chỉ từ event on-chain và kho file (SPEC mục 8, E3).

Dùng cho E3 và cho dashboard. Dashboard truyền `events` đã đọc theo khúc (RPC công khai giới hạn khoảng block của
eth_getLogs); E3 trên Hardhat đọc thẳng toàn dải.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd
from eth_utils import keccak
from web3.datastructures import AttributeDict

from rec.oracles.store import FileStore


def _logs(chain, contract, event: str, from_block: int = 0) -> list:
    ev = getattr(contract.events, event)
    return ev().get_logs(from_block=from_block)


def _args(chain, contract, event: str, events: dict | None) -> list:
    """Tham số của mọi event `event`. Có `events` (event đã đọc sẵn, ví dụ dashboard đọc log theo khúc vì RPC công khai
    giới hạn khoảng block) thì dùng luôn, không gọi lại eth_getLogs."""
    if events is not None:
        return [AttributeDict(e) for e in events[event]]
    return [lg.args for lg in _logs(chain, contract, event)]


def lineage(chain, store: FileStore, events: dict | None = None) -> pd.DataFrame:
    """Dựng lại chuỗi của từng chứng chỉ chỉ từ event on-chain và kho file."""
    registered = {bytes(a.deviceId) for a in _args(chain, chain.devices, "DeviceRegistered", events)}
    lots = {bytes(a.lotKey): a for a in _args(chain, chain.gate, "LotEvidenced", events)}
    reviews = {bytes(a.lotKey): a for a in _args(chain, chain.gate, "LotReview", events)}
    resolved = {bytes(a.lotKey): a for a in _args(chain, chain.gate, "LotResolved", events)}
    moves = defaultdict(list)
    for a in _args(chain, chain.certs, "TransferSingle", events):
        moves[int(a.id)].append((a["from"], a.to, int(a.value)))
    retired, withdrawn = defaultdict(int), defaultdict(int)
    for a in _args(chain, chain.certs, "Retired", events):
        retired[int(a.tokenId)] += int(a.wh)
    for a in _args(chain, chain.certs, "Withdrawn", events):  # Code Manager rút: đốt có event và lý do riêng
        withdrawn[int(a.tokenId)] += int(a.wh)
    rows = []
    for a in _args(chain, chain.gate, "Issued", events):
        tid, dev, day = int(a.tokenId), bytes(a.deviceId), int(a.day)
        cp = chain.devices.functions.deviceOf(dev).call()[0]
        key = keccak(bytes(cp) + day.to_bytes(32, "big"))
        lot = lots.get(key)
        files_ok = lot is not None and all(store.verify(bytes(r)) for r in lot.dataRoots if bytes(r) != b"\0" * 32)
        review_ok = True
        if lot is not None and lot.flags != 0:
            rv, rs = reviews.get(key), resolved.get(key)
            review_ok = rv is not None and rs is not None and rs.approved and (store.root / f"{bytes(rv.reasonsHash).hex()}.json").exists()
        bal = defaultdict(int)
        for frm, to, v in moves[tid]:
            if frm != "0x" + "0" * 40:
                bal[frm] -= v
            if to != "0x" + "0" * 40:
                bal[to] += v
        minted = sum(v for frm, _, v in moves[tid] if frm == "0x" + "0" * 40)
        burned = sum(v for _, to, v in moves[tid] if to == "0x" + "0" * 40)
        supply_ok = minted == int(a.wh) and burned == retired[tid] + withdrawn[tid] and all(v >= 0 for v in bal.values())
        rows.append({"token_id": hex(tid), "device": dev.rstrip(b"\0").decode(), "day": day,
                     "registered": dev in registered, "lot_evidence": lot is not None, "files_verified": files_ok,
                     "review_trail": review_ok, "supply_consistent": supply_ok, "transfers": len(moves[tid]) - 1,
                     "retired_wh": retired[tid], "withdrawn_wh": withdrawn[tid]})
    df = pd.DataFrame(rows)
    df["complete"] = df[["registered", "lot_evidence", "files_verified", "review_trail", "supply_consistent"]].all(axis=1)
    return df

"""Bằng chứng của lô cho backend chain: 4 nút oracle ký báo cáo, verifier (nếu có) chạy lớp B và ký verdict.

`make_verdict(...)` trả hàm `verdict_of(cp, day, reports)` mà `run_stream` gọi khi gặp sự kiện bằng chứng của lô.
Dùng chung cho E3 (`rec/experiments/e3.py`) và chain demo (`rec/deploy/demo.py`).
"""
from __future__ import annotations

from rec.gate.verifier import Verifier
from rec.oracles.node import oracle_nodes
from rec.oracles.store import FileStore
from rec.registry.base import LotEvidence
from rec.schema import OracleId

ORDER = (OracleId.O1, OracleId.O2, OracleId.O3, OracleId.O4)


def make_verdict(verifier: Verifier | None, data, temps, slot_ends, chain, store: FileStore):
    """Bằng chứng của lô: 4 nút oracle độc lập (rec/oracles/node.py) mỗi nút tự lưu chuỗi 15 phút của mình vào kho
    và tự ký báo cáo; verifier (nếu có) chạy lớp B trên cùng chuỗi đó."""
    cp = next(iter(chain.plant.cp_capacity_w))
    nodes = oracle_nodes(cp, chain.gate.address, chain.w3.eth.chain_id, chain.mnemonic, store)

    def verdict_of(cp: str, day: int, reports):
        dd = data[day]
        signed = tuple(nodes[o].observe(day, dd.series[o], dd.sun, slot_ends.get(day)) for o in ORDER)
        assert [r.data_root for r in signed] == [r.data_root for r in reports]  # khớp báo cáo trong dòng sự kiện
        if verifier is None:
            return LotEvidence(cp, day, signed, 0, int(dd.sun.sum()))
        v = verifier.evaluate(day, dd.series, dd.sun, temps[day])
        return LotEvidence(cp, day, signed, v.flags, v.sun_slots, v.ceiling_wh, v.model_hash, store.put_json(v.reasons))
    return verdict_of

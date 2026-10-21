"""DecisionGate mô phỏng off-chain: lớp A (công suất, ngân sách) và lớp B (cờ REVIEW) cho một lô (FLOW mục 4).

Dùng cho E2 và ablation. Test parity sẽ so kết quả với contract trên chain (giai đoạn 5).
Khóa (thiết bị, ngày) không cần ở E2, vì mỗi ca là một lô riêng không có yêu cầu trùng.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rec.oracles.encoding import MISSING, to_ints
from rec.schema import OracleId

SLOT_HOURS = 0.25
CHECKED_ORACLES = (OracleId.O1, OracleId.O2, OracleId.O3)  # O4 do issuer vận hành, không bị sửa


@dataclass(frozen=True)
class Profile:
    name: str
    completeness: bool
    consistency: bool
    ceiling: str | None  # None, "pv", "ai", "ai_linear", "ai_o3"


PROFILES = {
    "B1": Profile("B1", False, False, None),
    "B2": Profile("B2", True, True, "pv"),
    "Proposed": Profile("Proposed", True, True, "ai"),
    "A1": Profile("A1", True, True, "ai_o3"),
    "A2": Profile("A2", True, True, "ai_linear"),
}


def o1_report(values: np.ndarray) -> tuple[int, int]:
    """(Wh của ngày, Wh slot lớn nhất) theo đúng cách oracle báo cáo."""
    ints = [v for v in to_ints(values) if v != MISSING]
    return sum(ints), max(ints, default=0)


def layer_a(requests: list[tuple[str, str, int]], o1_day: int, o1_max_slot: int, sun_slots: int,
            device_cap_w: dict[str, int], cp_cap_w: int) -> list[str | None]:
    """Lý do REJECT của từng yêu cầu (None = qua lớp A), theo thứ tự gửi.

    Cùng thứ tự với DecisionGate.issue (FLOW mục 4): ② ngân sách trước, rồi ③ công suất của thiết bị và của lô.
    """
    lot_over = o1_max_slot > cp_cap_w * SLOT_HOURS or o1_day > cp_cap_w * sun_slots * SLOT_HOURS
    out, issued = [], 0
    for _, device, wh in requests:
        if issued + wh > o1_day:
            out.append("budget")
        elif lot_over or wh > device_cap_w[device] * sun_slots * SLOT_HOURS:
            out.append("capacity")  # vượt công suất thiết bị, hoặc báo cáo O1 vượt giới hạn vật lý của CP
        else:
            out.append(None)
            issued += wh
    return out


def device_caps(devices: dict[str, list[int]], inverter_w: int) -> dict[str, int]:
    """Công suất AC của thiết bị thật và của thiết bị giả trong D4b (`XD4b-<số khối>`)."""
    caps = {name: inverter_w * len(members) for name, members in devices.items()}
    per_block = inverter_w * len(next(iter(devices.values())))
    for m in range(1, len(devices) + 1):
        caps[f"XD4b-{m}"] = per_block * m
    return caps

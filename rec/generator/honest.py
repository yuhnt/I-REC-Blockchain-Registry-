"""Dòng sự kiện hợp lệ: đăng ký, báo cáo oracle, yêu cầu phát hành, chuyển nhượng, retire (SPEC mục 4–5).

Hai biến thể:
- "devices": 6 thiết bị B1–B6 ở issuerA; có L3 (B6 chuyển đăng ký sang issuerB giữa kỳ).
- "group": một Production Group thay cho 6 thiết bị (L4).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from rec.generator.common import (INVERTER_MAX_W, NOON, REPORT_AT, REQUEST_AT, DayData, allocate, local_t,
                                  reports_for)
from rec.schema import (Device, Event, EventKind, IssueRequest, Label, LabelKind, RegistrationTransfer, Retire,
                        Transfer)
from rec.timeutil import day_date

BUYERS = ("buyer1", "buyer2", "buyer3")
PLANT = "plant"
DAY_S = 86_400


@dataclass
class Issued:
    req_id: str
    device_id: str
    day: int
    wh: int
    issuer: str
    t: int


@dataclass
class HonestStream:
    events: list[Event] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    issued: list[Issued] = field(default_factory=list)
    retired: list[tuple[Issued, str, int]] = field(default_factory=list)  # (chứng chỉ, người retire, thời điểm)
    issuer_of: dict[str, list[tuple[int, str]]] = field(default_factory=dict)  # thiết bị → [(từ ngày, issuer)]

    def issuer_on(self, device_id: str, day: int) -> str:
        current = None
        for start, issuer in self.issuer_of[device_id]:
            if day >= start:
                current = issuer
        return current


def honest_stream(days: list[int], data: dict[int, DayData], plant: dict, seed: int, cfg: dict,
                  variant: str = "devices") -> HonestStream:
    rng = np.random.default_rng(seed)
    cp, (issuer_a, issuer_b) = plant["cp_id"], plant["issuers"]
    out = HonestStream()
    first = days[0]
    t_reg = local_t(first - 1, NOON)

    if variant == "group":
        cap = INVERTER_MAX_W * sum(len(v) for v in plant["devices"].values())
        out.events.append(Event(t_reg, EventKind.REGISTER, Device(
            "G1", cp, cap, issuer_a, effective_day=first, is_group=True, member_count=len(plant["devices"]))))
        out.issuer_of["G1"] = [(first, issuer_a)]
        weights_of = {"G1": None}
    else:
        for name, members in plant["devices"].items():
            out.events.append(Event(t_reg, EventKind.REGISTER, Device(
                name, cp, INVERTER_MAX_W * len(members), issuer_a, effective_day=first)))
            out.issuer_of[name] = [(first, issuer_a)]
        weights_of = {name: name for name in plant["devices"]}
        # L3: B6 chuyển đăng ký sang issuerB từ ngày giữa kỳ, giữ nguyên mã thiết bị (I-REC §16.3).
        mid = days[len(days) // 2]
        out.events.append(Event(local_t(mid - 1, NOON), EventKind.TRANSFER_REGISTRATION,
                                RegistrationTransfer("B6", issuer_a, issuer_b, mid)))
        out.issuer_of["B6"].append((mid, issuer_b))

    for d in days:
        dd = data[d]
        t_rep = local_t(d + 1, REPORT_AT)
        for rep in reports_for(dd, cp):
            out.events.append(Event(t_rep, EventKind.REPORT, rep))
        if variant == "group":
            shares = {"G1": dd.y_wh}
        else:
            shares = allocate(dd.y_wh, {n: dd.block_wh.get(n, 0.0) for n in weights_of})
        for i, (dev, wh) in enumerate(shares.items()):
            if wh <= 0:
                continue
            issuer = out.issuer_on(dev, d)
            req_id = f"h-{d}-{dev}"
            t_req = local_t(d + 1, REQUEST_AT) + i
            out.events.append(Event(t_req, EventKind.REQUEST, IssueRequest(req_id, issuer, dev, d, (wh,))))
            scenario = "L4" if variant == "group" else ("L3" if issuer == issuer_b else "honest")
            kind = LabelKind.HONEST if scenario == "honest" else LabelKind.L
            out.labels.append(Label(req_id, scenario, kind))
            item = Issued(req_id, dev, d, wh, issuer, t_req)
            out.issued.append(item)
            _lifecycle(out, item, rng, cfg, d)

    out.events.sort(key=lambda e: e.t)
    return out


def _lifecycle(out: HonestStream, item: Issued, rng, cfg: dict, day: int) -> None:
    """Chuyển nhượng và retire theo `honest_stream` trong scenarios.yaml."""
    if rng.random() >= cfg["transfer_prob"]:
        return
    lo, hi = cfg["transfer_delay_days"]
    t_tr = item.t + int(rng.integers(lo, hi + 1)) * DAY_S + NOON
    buyer = BUYERS[int(rng.integers(len(BUYERS)))]
    out.events.append(Event(t_tr, EventKind.TRANSFER, Transfer(item.device_id, day, PLANT, buyer, item.wh)))
    if rng.random() >= cfg["retire_prob"]:
        return
    lo, hi = cfg["retire_delay_days"]
    t_rt = t_tr + int(rng.integers(lo, hi + 1)) * DAY_S
    year = str(day_date(day).year)
    out.events.append(Event(t_rt, EventKind.RETIRE, Retire(
        item.device_id, day, buyer, item.wh, f"{buyer} (ESG)", "Scope 2", "California, US", year)))
    out.retired.append((item, buyer, t_rt))

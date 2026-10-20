"""Kịch bản tấn công của E1 (chế độ R1): D1–D6 và insider, chèn chồng lên dòng hợp lệ (SPEC mục 4.1).

Mỗi kịch bản chèn vào `cases_per_attack` ngày test ngẫu nhiên; tham số chia đều giữa các ca.
Ở R1 công tơ do điện lực giữ, nên kẻ gian không sửa được báo cáo O1: mọi kịch bản chỉ thêm, thay
hoặc sửa yêu cầu và thao tác vòng đời.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from rec.generator.common import INVERTER_MAX_W, REQUEST_AT, DayData, allocate, local_t
from rec.generator.honest import BUYERS, DAY_S, HonestStream, Issued
from rec.schema import (Device, EditAction, Event, EventKind, IssueRequest, Label, LabelKind, OperatorEdit, Retire,
                        Transfer)
from rec.timeutil import day_date


@dataclass
class Overlay:
    events: list[Event] = field(default_factory=list)
    labels: list[Label] = field(default_factory=list)
    removed: set[str] = field(default_factory=set)  # yêu cầu hợp lệ bị thay thế (D5)


def _split(n: int, options: list) -> list:
    """Chia n ca đều cho các lựa chọn tham số, theo thứ tự."""
    return [options[i * len(options) // n] for i in range(n)]


def e1_overlay(scenario: str, honest: HonestStream, days: list[int], data: dict[int, DayData], plant: dict,
               params: dict, n: int, seed: int) -> Overlay:
    rng = np.random.default_rng(np.random.SeedSequence([seed, sum(map(ord, scenario))]))
    by_day: dict[int, list[Issued]] = defaultdict(list)
    for it in honest.issued:
        by_day[it.day].append(it)
    issuer_a, issuer_b = plant["issuers"]
    cp = plant["cp_id"]
    ov = Overlay()
    pick = lambda pool, k: [pool[i] for i in rng.choice(len(pool), size=min(k, len(pool)), replace=False)]

    def share_map(d: int) -> dict[str, int]:
        return {it.device_id: it.wh for it in by_day[d]}

    if scenario == "D1":
        for i, d in enumerate(pick(days, n)):
            it = by_day[d][int(rng.integers(len(by_day[d])))]
            rid = f"D1-{i}"
            ov.events.append(Event(it.t + 300, EventKind.REQUEST,
                                   IssueRequest(rid, it.issuer, it.device_id, d, (it.wh,))))
            ov.labels.append(Label(rid, "D1", LabelKind.D, it.wh))

    elif scenario == "D2":
        periods = _split(n, params["period_days"])
        day_set = set(days)
        for i, period in enumerate(periods):
            # kỳ nằm trọn trong tập test và trong một năm dương lịch, để chỉ thử luật khóa
            starts = [d for d in days if d + period - 1 <= days[-1]
                      and day_date(d).year == day_date(d + period - 1).year]
            d0 = starts[int(rng.integers(len(starts)))]
            dev = by_day[d0][int(rng.integers(len(by_day[d0])))].device_id
            whs = tuple(share_map(d).get(dev, 0) if d in day_set else 0 for d in range(d0, d0 + period))
            rid = f"D2-{i}"
            issuer = honest.issuer_on(dev, d0)
            ov.events.append(Event(local_t(d0 + period, REQUEST_AT) + 600, EventKind.REQUEST,
                                   IssueRequest(rid, issuer, dev, d0, whs)))
            ov.labels.append(Label(rid, "D2", LabelKind.D, sum(whs)))

    elif scenario == "D3":
        lo, hi = params["gap_days"]
        registered = set()
        for i, d in enumerate(pick(days, n)):
            cands = [it for it in by_day[d] if it.issuer == issuer_a]
            it = cands[int(rng.integers(len(cands)))]
            t = it.t + int(rng.integers(lo, hi + 1)) * DAY_S + 600
            if it.device_id not in registered:
                cap = INVERTER_MAX_W * len(plant["devices"][it.device_id])
                ov.events.append(Event(t - 60, EventKind.REGISTER,
                                       Device(it.device_id, cp, cap, issuer_b, effective_day=days[0])))
                registered.add(it.device_id)
            rid = f"D3-{i}"
            ov.events.append(Event(t, EventKind.REQUEST, IssueRequest(rid, issuer_b, it.device_id, d, (it.wh,))))
            ov.labels.append(Label(rid, "D3", LabelKind.D, it.wh))

    elif scenario in ("D4a", "D4b"):
        fs = _split(n, params["f"]) if scenario == "D4b" else [None] * n
        names = list(plant["devices"])
        for i, (d, f) in enumerate(zip(pick(days, n), fs)):
            shares = share_map(d)
            if scenario == "D4a":
                src = names[int(rng.integers(len(names)))]
                copied, cap = shares.get(src, 0), INVERTER_MAX_W * len(plant["devices"][src])
            else:
                m = max(1, round(len(names) * f))
                copied = sum(shares.get(b, 0) for b in names[:m])
                cap = INVERTER_MAX_W * sum(len(plant["devices"][b]) for b in names[:m])
            dev, rid = f"X{scenario}-{i}", f"{scenario}-{i}"
            t = local_t(d + 1, REQUEST_AT) + 900
            ov.events.append(Event(t - 60, EventKind.REGISTER, Device(dev, cp, cap, issuer_b, effective_day=d)))
            ov.events.append(Event(t, EventKind.REQUEST, IssueRequest(rid, issuer_b, dev, d, (copied,))))
            ov.labels.append(Label(rid, scenario, LabelKind.D, copied))

    elif scenario == "D5":
        targets = _split(n, params["target_day"])
        used = set()
        for i, kind in enumerate(targets):
            pool = [d for d in days if d not in used and _is_target(data[d], kind)
                    and any(x < d and data[x].y_wh > data[d].y_wh for x in days)]
            y = pool[int(rng.integers(len(pool)))]
            used.add(y)
            sources = [x for x in days if x < y and data[x].y_wh > data[y].y_wh]
            x = sources[int(rng.integers(len(sources)))]
            true_shares = share_map(y)
            fake = allocate(data[x].y_wh, data[x].block_wh)
            for it in by_day[y]:
                ov.removed.add(it.req_id)
                rid = f"D5-{i}-{it.device_id}"
                wh = fake.get(it.device_id, 0)
                ov.events.append(Event(it.t - 1, EventKind.REQUEST,
                                       IssueRequest(rid, it.issuer, it.device_id, y, (max(wh, 1),))))
                ov.labels.append(Label(rid, "D5", LabelKind.D, max(0, wh - true_shares.get(it.device_id, 0))))

    elif scenario == "D6":
        variants = _split(n, params["variant"])
        for i, (variant, (it, holder, t_rt)) in enumerate(zip(variants, pick(honest.retired, n))):
            ref = f"D6-{i}"
            if variant == "retire_twice":
                ev = Retire(it.device_id, it.day, holder, it.wh, f"{holder} (ESG)", "Scope 2", "California, US",
                            str(day_date(it.day).year), ref=ref)
                ov.events.append(Event(t_rt + DAY_S, EventKind.RETIRE, ev))
            else:
                other = next(b for b in BUYERS if b != holder)
                ov.events.append(Event(t_rt + DAY_S, EventKind.TRANSFER,
                                       Transfer(it.device_id, it.day, holder, other, it.wh, ref=ref)))
            ov.labels.append(Label(ref, "D6", LabelKind.D, it.wh))

    elif scenario == "insider":
        actions = _split(n, [EditAction(a) for a in params["action"]])
        for i, (action, it) in enumerate(zip(actions, pick(honest.issued, n))):
            ref = f"insider-{i}"
            ov.events.append(Event(it.t + 2 * DAY_S, EventKind.OPERATOR_EDIT,
                                   OperatorEdit(it.issuer, it.req_id, action, ref=ref)))
            excess = 0 if action is EditAction.DELETE else it.wh
            ov.labels.append(Label(ref, "insider", LabelKind.D, excess))

    else:
        raise ValueError(f"kịch bản E1 không xác định: {scenario}")

    ov.events.sort(key=lambda e: e.t)
    return ov


def _is_target(dd: DayData, kind: str) -> bool:
    if kind == "cloudy":
        return dd.day_type == "cloudy"
    if kind == "sunny_fault":
        return dd.day_type == "clear" and dd.outage
    raise ValueError(kind)

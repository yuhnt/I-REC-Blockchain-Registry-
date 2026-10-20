"""Bộ kiểm tra generator trước khi khóa tập test (SPEC mục 9). Mỗi hàm trả về danh sách lỗi (rỗng = qua)."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from rec.generator.cases_e2 import apply_case
from rec.generator.common import DayData
from rec.schema import Event, EventKind, OracleId


def check_clean_stream(events: list[Event]) -> list[str]:
    """Dòng hợp lệ phải có DCR = 0: không (thiết bị, ngày) nào xin hai lần, tổng xin ≤ O1, đúng issuer."""
    errors = []
    o1: dict[tuple[str, int], int] = {}
    cp_of: dict[str, str] = {}
    issuer_of: dict[str, list[tuple[int, str]]] = defaultdict(list)
    requested: dict[tuple[str, int], int] = defaultdict(int)
    seen: set[tuple[str, int]] = set()
    for e in events:
        p = e.payload
        if e.kind is EventKind.REGISTER:
            cp_of[p.device_id] = p.cp_id
            issuer_of[p.device_id].append((p.effective_day, p.issuer))
        elif e.kind is EventKind.TRANSFER_REGISTRATION:
            issuer_of[p.device_id].append((p.effective_day, p.to_issuer))
        elif e.kind is EventKind.REPORT and p.oracle is OracleId.O1:
            o1[(p.subject, p.day)] = p.wh_day
        elif e.kind is EventKind.REQUEST:
            for k, day in enumerate(p.days):
                key = (p.device_id, day)
                if key in seen:
                    errors.append(f"{p.req_id}: (thiết bị, ngày) {key} xin hai lần")
                seen.add(key)
                requested[(cp_of[p.device_id], day)] += p.wh_per_day[k]
                current = [iss for start, iss in sorted(issuer_of[p.device_id]) if start <= day]
                if not current or current[-1] != p.issuer:
                    errors.append(f"{p.req_id}: issuer {p.issuer} không phải issuer hiện tại của {p.device_id}")
    for key, total in requested.items():
        if total > o1.get(key, -1):
            errors.append(f"(CP, ngày) {key}: tổng xin {total} vượt O1 {o1.get(key)}")
    return errors


def check_time_order(events: list[Event]) -> list[str]:
    ts = [e.t for e in events]
    return [] if all(a <= b for a, b in zip(ts, ts[1:])) else ["sự kiện không theo thứ tự thời gian"]


def check_cases(cases: pd.DataFrame, labels: pd.DataFrame, data: dict[int, DayData], devices: list[str],
                sample: int = 2000, seed: int = 0) -> list[str]:
    """Trên một mẫu ca: định dạng như nhau (không thêm slot thiếu, trừ M3 mất dữ liệu và lệch giờ),
    giá trị không âm, lô trung thực không có phần vượt."""
    errors = []
    if labels.loc[labels["kind"].isin(["honest", "L"]), "excess_wh_true"].any():
        errors.append("lô trung thực có phần vượt khác 0")
    if not cases["case_id"].is_unique:
        errors.append("case_id bị trùng")
    rng = np.random.default_rng(seed)
    rows = cases.to_dict("records")
    for i in rng.choice(len(rows), size=min(sample, len(rows)), replace=False):
        row = rows[i]
        applied = apply_case(row, data, devices)
        dd = data[int(row["day"])]
        # Lỗi oracle (M3) được phép đổi số slot thiếu; D5 thay chuỗi bằng chuỗi của ngày khác.
        may_change_missing = row["scenario"] in ("M3", "D5")
        for o, v in applied.series.items():
            if np.nanmin(v, initial=0) < 0:
                errors.append(f"{row['case_id']}: {o.value} có giá trị âm")
            if not may_change_missing and np.isnan(v).sum() != np.isnan(dd.series[o]).sum():
                errors.append(f"{row['case_id']}: {o.value} đổi số slot thiếu")
            if len(v) != len(dd.sun):
                errors.append(f"{row['case_id']}: {o.value} sai số slot")
    return errors

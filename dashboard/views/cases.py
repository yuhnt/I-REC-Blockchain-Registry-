"""Truy vết kịch bản: mỗi kịch bản demo, điểm chặn kỳ vọng theo thiết kế so với kết quả đọc từ chain.

Trang dành cho người trình bày và người chấm, **không phải màn hình của auditor**: nó lộ nhãn kịch bản (lô nào bị
khai tăng), điều mà auditor không được thấy. Danh sách kịch bản lấy từ `deployment.json` → `scenarios` (do
`rec/deploy/demo.py` ghi); bản deploy cũ không có danh sách này thì suy ra từ mã yêu cầu và event.
Luật và mã lý do: docs/DECISION_RULES.md.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import state as S
from dashboard.components import certificate_detail, evidence_block
from dashboard.onchain import b32, s32, tx_cell, when
from dashboard.tables import (STATUS, cert_of, flags_text, held_info, lot_of, lot_status, pick, production_by_day,
                              show, token_of)
from rec.registry.contracts import REASONS
from rec.timeutil import day_date

CASES = {  # mã → (nhóm, tấn công / tình huống)
    "stream": ("Dòng hợp lệ", "dữ liệu thật của các ngày đầu, 6 thiết bị, issuerA gửi yêu cầu ngày d + 1"),
    "D1": ("Đếm trùng", "issuerA nộp lại (thiết bị, ngày) đã phát hành"),
    "D4a": ("Đếm trùng", "issuerB đăng ký thiết bị mới cùng CP, chép sản lượng của thiết bị đã có"),
    "M2-k1": ("Khai khống", "O1 khai tăng 45%; O2, O3 giữ số thật (k = 1)"),
    "M2-k3": ("Khai khống", "O1, O2, O3 cùng tăng 20% (k = 3)"),
    "honest": ("Mẫu âm", "lô trung thực, số liệu thật không sửa"),
    "code-manager": ("Xử lý lỗi (§11)", "chứng chỉ bị nghi: Code Manager tạm khóa rồi rút 10%"),
    "insider": ("Insider", "issuerA tự gọi withdraw để sửa sổ cái"),
}
EXPECT = {"mint": "MINT; lô REVIEW nhầm được auditor duyệt rồi MINT",
          "key": "Lớp A · khóa (thiết bị, ngày) → IssueRejected(KEY)",
          "budget": "Lớp A · ngân sách CP → IssueRejected(BUDGET)",
          "review": "Lớp B · lô vào REVIEW, yêu cầu bị giữ chờ auditor",
          "code_manager": "Suspended và Withdrawn on-chain, kèm lý do",
          "revert": "Giao dịch revert, sổ cái không đổi"}
AUDITOR_SHOULD = {"M2-k1": "bác (khai khống thật)", "M2-k3": "bác (khai khống thật)",
                  "honest": "duyệt (REVIEW nhầm)"}


def scenarios() -> list[dict]:
    """Danh sách kịch bản đã chạy; thêm dòng hợp lệ ở đầu."""
    out = [{"id": "stream", "kind": "stream", "expect": "mint"}]
    if "scenarios" in S.chain.dep:
        return out + S.chain.dep["scenarios"]
    # Bản deploy cũ: suy ra từ mã yêu cầu cố định của demo, nhãn trong held_requests và event Code Manager.
    for rid, sid, exp in (("demo-D1", "D1", "key"), ("demo-D4a", "D4a", "budget")):
        e = next((e for e in reversed(S.ev["IssueRejected"]) if s32(e["reqId"]) == rid), None)
        if e is not None:
            out.append({"id": sid, "kind": "request", "req_id": rid, "device": s32(e["deviceId"]),
                        "day": int(e["day"]), "expect": exp})
    seen = set()
    for r in S.chain.dep.get("held_requests", []):
        if r.get("scenario") and r["scenario"] not in seen:
            seen.add(r["scenario"])
            out.append({"id": r["scenario"], "kind": "lot", "day": r["day"], "expect": "review"})
    sus = next(iter(S.ev["Suspended"]), None)
    if sus is not None and int(sus["tokenId"]) in cert_of():
        dev, day = cert_of()[int(sus["tokenId"])]
        out.append({"id": "code-manager", "kind": "code_manager", "device": dev, "day": day})
    return out


def _attempts(keep) -> dict[str, list[tuple[str, dict]]]:
    """Mọi lần gửi của từng yêu cầu, theo thứ tự block. Một reqId có thể xuất hiện nhiều lần: issuer gửi lại sau khi
    auditor duyệt, hoặc demo được chạy lại sau một lần hỏng (trên Sepolia, lần đầu lỗi chainId → ORACLE)."""
    out: dict[str, list] = {}
    for kind, name in (("reject", "IssueRejected"), ("mint", "Issued"), ("held", "IssueHeld")):
        for e in S.ev[name]:
            rid = s32(e["reqId"])
            if keep(rid):
                out.setdefault(rid, []).append((kind, e))
    return {rid: sorted(v, key=lambda x: x[1]["block"]) for rid, v in out.items()}


def _check(c: dict) -> dict:
    """Kết quả on-chain của một kịch bản: (mô tả, có khớp kỳ vọng không, block, tx)."""
    ev = S.ev
    if c["kind"] == "stream":
        tries = _attempts(lambda rid: rid.startswith("h-"))
        final = [v[-1] for v in tries.values()]
        n = {k: sum(1 for kind, _ in final if kind == k) for k in ("mint", "reject", "held")}
        retried = sum(1 for v in tries.values() for kind, _ in v[:-1] if kind == "reject")
        approved = sum(1 for e in ev["LotResolved"] if e["approved"])
        last = max((e for _, e in final), key=lambda e: e["block"], default=None)
        note = f" (thêm {retried} lần gửi trước đó bị từ chối rồi gửi lại)" if retried else ""
        return {"result": f"{n['mint']} yêu cầu MINT, {n['reject']} bị từ chối, {n['held']} đang giữ, "
                          f"{approved} lô được duyệt{note}",
                "ok": n["mint"] > 0 and n["reject"] == 0, "block": last["block"] if last else None,
                "tx": last["tx"] if last else None}
    if c["kind"] == "request":
        tries = _attempts(lambda rid: rid == c["req_id"]).get(c["req_id"], [])
        if not tries:
            return {"result": "không thấy event", "ok": False, "block": None, "tx": None}
        kind, e = tries[-1]  # kết cục của lần gửi cuối
        note = f" (lần gửi thứ {len(tries)})" if len(tries) > 1 else ""
        if kind == "reject":
            code = REASONS[int(e["reason"])].value
            return {"result": f"IssueRejected({code.upper()}){note}", "ok": code == c["expect"], "block": e["block"],
                    "tx": e["tx"]}
        return {"result": ("MINT (lọt)" if kind == "mint" else "bị giữ") + note, "ok": False, "block": e["block"],
                "tx": e["tx"]}
    if c["kind"] == "lot":
        key, lot = lot_of(S.CP, c["day"])
        if lot is None:
            return {"result": "chưa có bằng chứng", "ok": False, "block": None, "tx": None}
        flags = int(lot["flags"])
        return {"result": f"cờ: {flags_text(flags)} · lô {STATUS[lot_status(key)]}", "ok": flags != 0,
                "block": lot["block"], "tx": lot["tx"]}
    if c["kind"] == "code_manager":
        tid = token_of(c["device"], c["day"])
        sus = [e for e in ev["Suspended"] if int(e["tokenId"]) == tid]
        wd = [e for e in ev["Withdrawn"] if int(e["tokenId"]) == tid]
        last = (sus + wd)[-1] if sus or wd else None
        return {"result": f"{len(sus)} Suspended, rút {sum(e['wh'] for e in wd) / 1000:,.1f} kWh",
                "ok": bool(sus and wd), "block": last["block"] if last else None, "tx": last["tx"] if last else None}
    # insider: giao dịch revert không để lại event; kết quả lấy từ lúc chạy demo.
    return {"result": f"{c.get('outcome', '?')} ({c.get('reason', '')}), không có event",
            "ok": c.get("outcome") == "revert", "block": None, "tx": None}


def _detail(c: dict) -> None:
    ev = S.ev
    group, text = CASES.get(c["id"], ("", ""))
    st.markdown(f"#### {c['id']} · {group}: {text}")
    if c["kind"] == "stream":
        st.write("Mỗi ngày: 4 oracle báo cáo lúc 00:30, issuer gửi bằng chứng của lô lúc 00:45, yêu cầu MINT cho từng "
                 "thiết bị lúc 01:00; lô REVIEW được auditor xử lý lúc 23:00 ngày d + 1.")
        show(production_by_day(S.CP), hide=("day",))
    elif c["kind"] == "request":
        day = c.get("day")
        st.write(f"Yêu cầu `{c['req_id']}` cho thiết bị **{c.get('device', '?')}**, ngày sản xuất "
                 f"{day_date(day) if day else '?'}" + (f", {c['wh'] / 1000:,.1f} kWh" if "wh" in c else "") + ".")
        if c["expect"] == "key" and day:
            st.write("Khóa (thiết bị, ngày) đã có chứng chỉ dưới đây, nên contract từ chối trước khi xét ngân sách:")
            tid = token_of(c["device"], day)
            if tid is not None:
                certificate_detail(tid)
        elif c["expect"] == "budget" and day:
            key, lot = lot_of(S.CP, day)
            used = S.chain.certs.functions.issuedWh(b32(S.CP), day).call()
            if lot:
                c1, c2, c3 = st.columns(3)
                c1.metric("O1 của lô (ngân sách CP)", f"{lot['o1Wh'] / 1000:,.1f} kWh")
                c2.metric("Đã phát hành cho CP trong ngày", f"{used / 1000:,.1f} kWh")
                c3.metric("Yêu cầu thêm", f"{c['wh'] / 1000:,.1f} kWh" if "wh" in c else "—")
                st.write("Đã phát hành + yêu cầu thêm > O1, nên contract từ chối với `BUDGET`. Thiết bị mới có mã khác "
                         "nên khóa (thiết bị, ngày) không chặn được; chặn được là nhờ ngân sách gắn với CP"
                         + (f" (chép sản lượng của {c['copied_from']})." if "copied_from" in c else "."))
                evidence_block(key, lot)
    elif c["kind"] == "lot":
        key, lot = lot_of(S.CP, c["day"])
        st.write(f"Auditor nên: **{AUDITOR_SHOULD.get(c['id'], '—')}**. Auditor không thấy nhãn này; họ chỉ thấy "
                 "bằng chứng bên dưới.")
        reqs = [r for r in held_info().values() if r.get("scenario") == c["id"]]
        if reqs:
            show(pd.DataFrame([{"yêu cầu": r["req_id"], "thiết bị": r["device"], "lượng xin (kWh)": r["wh"] / 1000,
                                "đã phát hành": S.chain.certs.functions.keyUsed(b32(r["device"]), r["day"]).call()}
                               for r in reqs]))
        if lot:
            evidence_block(key, lot)
    elif c["kind"] == "code_manager":
        tid = token_of(c["device"], c["day"])
        if tid is not None:
            certificate_detail(tid)
    else:
        st.write("Contract không có hàm sửa, xóa hay phát hành lại. Thao tác gần nhất issuer thử được là gọi "
                 "`CertificateRegistry.withdraw` (chỉ Code Manager được gọi); giao dịch revert `NotCodeManager`, "
                 "không có event, số dư không đổi.")
        st.code("certs.withdraw(tokenId, plant, 1, \"insider\")   # gửi từ issuerA → revert NotCodeManager")
        st.metric("Event Withdrawn có lý do \"insider\"", sum(1 for e in ev["Withdrawn"] if e["reason"] == "insider"))


def render() -> None:
    st.title("Truy vết kịch bản")
    st.caption("Mỗi dòng là một kịch bản đã chạy trên chain này: điểm chặn kỳ vọng theo thiết kế "
               "(docs/DECISION_RULES.md) so với kết quả đọc từ event. Trang này lộ nhãn kịch bản, dành cho người trình "
               "bày; auditor làm việc ở trang Production Auditor, nơi không có nhãn.")
    cases = scenarios()
    rows = []
    for c in cases:
        r = _check(c)
        group, text = CASES.get(c["id"], ("", ""))
        rows.append({"kịch bản": c["id"], "nhóm": group, "tình huống": text,
                     "điểm chặn kỳ vọng": EXPECT.get(c.get("expect", c["kind"]), ""), "kết quả on-chain": r["result"],
                     "khớp": "✔" if r["ok"] else "✘", "thời điểm": when(r["block"]) if r["block"] else "—",
                     "giao dịch": tx_cell(r["tx"]) if r["tx"] else "—"})
    df = pd.DataFrame(rows)
    n_ok = int((df["khớp"] == "✔").sum())
    st.metric("Kịch bản khớp kỳ vọng", f"{n_ok}/{len(df)}")
    st.caption("Bấm vào một dòng để xem bằng chứng: event, chứng chỉ liên quan, 4 báo cáo oracle.")
    i = pick(df, "cases-cases")
    if i is not None:
        _detail(cases[i])

"""Đối tượng dùng chung giữa generator, lớp B, registry và metrics (PLAN.md mục 3.2).

Quy ước:
- Năng lượng là số nguyên Wh.
- Ngày là số ngày địa phương của nhà máy kể từ 1970-01-01 (xem rec.timeutil).
- Mã định danh (thiết bị, CP, issuer, chủ sở hữu) là chuỗi; tầng chain tự đổi sang bytes32/address.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntFlag


class OracleId(str, Enum):
    O1 = "O1"  # công tơ tại điểm đấu nối (CP)
    O2 = "O2"  # tổng công suất inverter
    O3 = "O3"  # bức xạ POA tại chỗ
    O4 = "O4"  # bức xạ vệ tinh NSRDB (nguồn độc lập)


class Regime(str, Enum):
    R1 = "R1"  # khóa O1 thuộc điện lực: kẻ gian không ký được O1 đã sửa
    R2 = "R2"  # khóa O1–O3 thuộc chủ dự án


class Flag(IntFlag):
    """Cờ của lớp B; khác 0 nghĩa là REVIEW (luật ④)."""

    NONE = 0
    INCONSISTENT = 1  # luật (a): O1/O2/O3 lệch nhau
    HISTORY_MATCH = 2  # luật (c): khớp một ngày đã phát hành
    OVER_CEILING = 4  # luật (b) trần pvlib hoặc trần C của AI


class DecisionKind(str, Enum):
    REJECT = "REJECT"
    REVIEW = "REVIEW"
    MINT = "MINT"


class RejectReason(str, Enum):
    KEY = "key"  # ①: (thiết bị, ngày) đã phát hành
    BUDGET = "budget"  # ②: vượt ngân sách CP
    CAPACITY = "capacity"  # ③: vượt luật công suất
    ORACLE = "oracle"  # chữ ký không hợp lệ, hoặc O1 xung đột với O1 đã lưu


class EventKind(str, Enum):
    REGISTER = "register"
    REPORT = "report"
    REQUEST = "request"
    TRANSFER = "transfer"
    RETIRE = "retire"
    OPERATOR_EDIT = "operator_edit"  # kịch bản insider, chỉ B0 thực hiện được


class LabelKind(str, Enum):
    HONEST = "honest"
    D = "D"  # double counting
    M = "M"  # khai khống, oracle lỗi
    L = "L"  # bất thường hợp lệ (mẫu âm khó)


def batch_key(device_id: str, day: int) -> str:
    """Khóa của một batch (thiết bị × ngày), cũng là định danh token ERC-1155 ở tầng chain."""
    return f"{device_id}:{day}"


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} phải là chuỗi khác rỗng")


def _require_wh(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} phải là số nguyên Wh không âm, nhận {value!r}")


def _require_day(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} phải là số ngày không âm, nhận {value!r}")


@dataclass(frozen=True, slots=True)
class Device:
    device_id: str
    cp_id: str
    ac_capacity_w: int
    issuer: str

    def __post_init__(self) -> None:
        _require_id("device_id", self.device_id)
        _require_id("cp_id", self.cp_id)
        _require_id("issuer", self.issuer)
        _require_wh("ac_capacity_w", self.ac_capacity_w)
        if self.ac_capacity_w == 0:
            raise ValueError("ac_capacity_w phải dương")


@dataclass(frozen=True, slots=True)
class IssueRequest:
    """Yêu cầu phát hành cho một thiết bị, có thể gồm nhiều ngày liên tiếp (kịch bản D2)."""

    req_id: str
    issuer: str
    device_id: str
    day_start: int
    wh_per_day: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_id("req_id", self.req_id)
        _require_id("issuer", self.issuer)
        _require_id("device_id", self.device_id)
        _require_day("day_start", self.day_start)
        if not isinstance(self.wh_per_day, tuple) or not self.wh_per_day:
            raise ValueError("wh_per_day phải là tuple khác rỗng")
        for wh in self.wh_per_day:
            _require_wh("wh_per_day", wh)

    @property
    def days(self) -> range:
        return range(self.day_start, self.day_start + len(self.wh_per_day))

    @property
    def total_wh(self) -> int:
        return sum(self.wh_per_day)


@dataclass(frozen=True, slots=True)
class OracleReport:
    """Báo cáo ngày của một oracle. `subject` là cp_id với O1, O4 và là device_id với O2, O3."""

    oracle: OracleId
    subject: str
    day: int
    wh_day: int
    max_slot_wh: int
    data_root: bytes = b""  # hash chuỗi 15 phút; chuỗi đầy đủ nằm off-chain
    signature: bytes = b""

    def __post_init__(self) -> None:
        if not isinstance(self.oracle, OracleId):
            raise ValueError("oracle phải là OracleId")
        _require_id("subject", self.subject)
        _require_day("day", self.day)
        _require_wh("wh_day", self.wh_day)
        _require_wh("max_slot_wh", self.max_slot_wh)
        if self.max_slot_wh > self.wh_day:
            raise ValueError("max_slot_wh không thể lớn hơn wh_day")
        if self.data_root and len(self.data_root) != 32:
            raise ValueError("data_root phải rỗng hoặc dài 32 byte")


@dataclass(frozen=True, slots=True)
class Verdict:
    """Kết quả lớp B cho một batch, do verifier của issuer ký kèm hash mô hình."""

    batch_key: str
    flags: Flag
    ceiling_wh: int | None
    model_hash: str
    reasons: tuple[str, ...] = ()
    signature: bytes = b""

    def __post_init__(self) -> None:
        _require_id("batch_key", self.batch_key)
        if not isinstance(self.flags, Flag):
            raise ValueError("flags phải là Flag")
        if self.ceiling_wh is not None:
            _require_wh("ceiling_wh", self.ceiling_wh)

    @property
    def needs_review(self) -> bool:
        return self.flags != Flag.NONE


@dataclass(frozen=True, slots=True)
class Decision:
    kind: DecisionKind
    reason: RejectReason | None = None
    flags: Flag = Flag.NONE
    wh: int = 0

    def __post_init__(self) -> None:
        if self.kind is DecisionKind.REJECT:
            ok = self.reason is not None and self.flags == Flag.NONE and self.wh == 0
        elif self.kind is DecisionKind.REVIEW:
            ok = self.reason is None and self.flags != Flag.NONE and self.wh == 0
        else:
            ok = self.reason is None and self.flags == Flag.NONE and self.wh > 0
        if not ok:
            raise ValueError(f"Decision không hợp lệ: {self!r}")

    @classmethod
    def reject(cls, reason: RejectReason) -> Decision:
        return cls(DecisionKind.REJECT, reason=reason)

    @classmethod
    def review(cls, flags: Flag) -> Decision:
        return cls(DecisionKind.REVIEW, flags=flags)

    @classmethod
    def mint(cls, wh: int) -> Decision:
        return cls(DecisionKind.MINT, wh=wh)


@dataclass(frozen=True, slots=True)
class Transfer:
    device_id: str
    day: int
    sender: str
    recipient: str
    wh: int

    def __post_init__(self) -> None:
        for name in ("device_id", "sender", "recipient"):
            _require_id(name, getattr(self, name))
        _require_day("day", self.day)
        _require_wh("wh", self.wh)


@dataclass(frozen=True, slots=True)
class Retire:
    device_id: str
    day: int
    holder: str
    wh: int
    beneficiary: str

    def __post_init__(self) -> None:
        for name in ("device_id", "holder", "beneficiary"):
            _require_id(name, getattr(self, name))
        _require_day("day", self.day)
        _require_wh("wh", self.wh)


class EditAction(str, Enum):
    UPDATE = "update"
    DELETE = "delete"
    REISSUE = "reissue"


@dataclass(frozen=True, slots=True)
class OperatorEdit:
    """Người vận hành registry sửa, xóa hoặc phát hành lại một bản ghi đã phát hành (insider)."""

    issuer: str
    target_req_id: str
    action: EditAction

    def __post_init__(self) -> None:
        _require_id("issuer", self.issuer)
        _require_id("target_req_id", self.target_req_id)
        if not isinstance(self.action, EditAction):
            raise ValueError("action phải là EditAction")


_PAYLOAD_TYPES: dict[EventKind, type] = {
    EventKind.REGISTER: Device,
    EventKind.REPORT: OracleReport,
    EventKind.REQUEST: IssueRequest,
    EventKind.TRANSFER: Transfer,
    EventKind.RETIRE: Retire,
    EventKind.OPERATOR_EDIT: OperatorEdit,
}


@dataclass(frozen=True, slots=True)
class Event:
    """Một sự kiện trong dòng do generator sinh. `t` là giây mô phỏng kể từ 1970-01-01 UTC."""

    t: int
    kind: EventKind
    payload: Device | OracleReport | IssueRequest | Transfer | Retire | OperatorEdit

    def __post_init__(self) -> None:
        if isinstance(self.t, bool) or not isinstance(self.t, int) or self.t < 0:
            raise ValueError("t phải là số nguyên giây không âm")
        expected = _PAYLOAD_TYPES[self.kind]
        if not isinstance(self.payload, expected):
            raise ValueError(f"sự kiện {self.kind.value} cần payload {expected.__name__}")


@dataclass(frozen=True, slots=True)
class Label:
    """Nhãn ẩn của một yêu cầu. Chỉ rec.metrics và Production Auditor mô phỏng được đọc."""

    req_id: str
    scenario: str
    kind: LabelKind
    excess_wh_true: int = 0  # phần phát hành vượt sản lượng thật tại (CP, ngày) do yêu cầu này gây ra

    def __post_init__(self) -> None:
        _require_id("req_id", self.req_id)
        _require_id("scenario", self.scenario)
        _require_wh("excess_wh_true", self.excess_wh_true)
        if self.kind in (LabelKind.HONEST, LabelKind.L) and self.excess_wh_true != 0:
            raise ValueError("yêu cầu trung thực hoặc bất thường hợp lệ không có phần vượt")

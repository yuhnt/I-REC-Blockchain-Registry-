"""Interface chung của ba backend lớp A: b0_separate, b0_shared (SQLite) và chain (FLOW.md mục 10).

E1 chạy cùng một dòng sự kiện qua cả ba backend; runner chỉ gọi các hàm dưới đây và ghi `Outcome` vào nhật ký.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from rec.schema import (Deregistration, Device, IssueRequest, OperatorEdit, OracleReport, RegistrationTransfer,
                        RejectReason, Retire, Transfer)

SLOTS_PER_HOUR = 4
DAY_END_OFFSET_S = 7 * 3600  # ngày d coi là kết thúc lúc 00:00 PDT ngày d + 1 (như DecisionGate)
DAY_S = 86_400


@dataclass(frozen=True)
class Outcome:
    """Kết quả một thao tác.

    kind: "ok" (thao tác thành công), "mint", "reject" (lớp A từ chối, có lý do), "held" (lô đang REVIEW),
    "revert" (thao tác bị chặn trước khi ghi, ví dụ mã thiết bị trùng hoặc không có quyền).
    """

    kind: str
    reason: str = ""
    minted: tuple[tuple[str, int, int], ...] = ()  # (thiết bị, ngày, Wh) đã mint
    trace: bool = True  # thao tác có để lại bản ghi công khai không (insider)
    gas: int = 0
    tx: str = ""

    @property
    def minted_wh(self) -> int:
        return sum(wh for _, _, wh in self.minted)


@dataclass(frozen=True)
class LotEvidence:
    """Bằng chứng của một lô: 4 báo cáo (None = thiếu) và verdict của lớp B."""

    cp_id: str
    day: int
    reports: tuple[OracleReport | None, ...]
    flags: int
    sun_slots: int
    ceiling_wh: int = 0
    model_hash: bytes = b"\0" * 32
    reasons_hash: bytes = b"\0" * 32

    @property
    def o1(self) -> OracleReport:
        return self.reports[0]


@dataclass
class Plant:
    """Thông số đã xác minh khi deploy (allowlist và công suất CP)."""

    cp_capacity_w: dict[str, int]
    holder_of: dict[str, str]
    issuers: tuple[str, ...]
    accounts: dict[str, int] = field(default_factory=dict)  # tên → chỉ số tài khoản Hardhat (chỉ backend chain)


def reject(reason: RejectReason) -> Outcome:
    return Outcome("reject", reason.value)


class Registry(ABC):
    name: str

    @abstractmethod
    def register_device(self, dev: Device, t: int) -> Outcome: ...

    @abstractmethod
    def transfer_registration(self, rt: RegistrationTransfer, t: int) -> Outcome: ...

    @abstractmethod
    def close_registration(self, dr: Deregistration, t: int) -> Outcome: ...

    @abstractmethod
    def submit_lot_evidence(self, ev: LotEvidence, issuer: str, t: int) -> Outcome: ...

    @abstractmethod
    def resolve_review(self, cp_id: str, day: int, approve: bool, t: int) -> Outcome: ...

    @abstractmethod
    def issue(self, req: IssueRequest, t: int) -> Outcome: ...

    @abstractmethod
    def transfer(self, tr: Transfer, t: int) -> Outcome: ...

    @abstractmethod
    def retire(self, rt: Retire, t: int) -> Outcome: ...

    @abstractmethod
    def suspend(self, device_id: str, day: int, active: bool, reason: str, t: int) -> Outcome: ...

    @abstractmethod
    def withdraw(self, device_id: str, day: int, holder: str, wh: int, reason: str, t: int) -> Outcome: ...

    @abstractmethod
    def operator_edit(self, edit: OperatorEdit, t: int) -> Outcome:
        """Kịch bản insider: người vận hành sửa, xóa hoặc phát hành lại bản ghi đã phát hành."""

    def reconcile(self, t: int) -> list[dict]:
        """Đối soát chéo (chỉ b0_separate); các backend khác không cần."""
        return []

    def close(self) -> None:
        pass

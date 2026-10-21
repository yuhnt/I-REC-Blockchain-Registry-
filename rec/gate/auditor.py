"""Production Auditor mô phỏng (SPEC mục 6.3, 8.2; FLOW mục 5–6).

Hai việc:
1. **Phân xử lô REVIEW (cách B):** duyệt nếu lô không khai khống, bác nếu có. Giả định auditor luôn kết luận đúng,
   nên chỉ đọc nhãn thật của đúng lô đang xét.
2. **Kiểm tra ngẫu nhiên p% số lô đã MINT,** lúc 12:00 ngày d + 2. Lô gian lận bị bốc trúng thì bị phát hiện chắc
   chắn; Code Manager rút phần chứng chỉ chưa retire. Phần đã retire trước lúc kiểm thì không rút được, và tính là lọt.

Bốc thăm dùng một số ngẫu nhiên u ∈ [0, 1) cố định cho mỗi lô: lô được kiểm khi u < p. Nhờ vậy tập lô được kiểm ở
p = 1% nằm trong tập ở p = 5%, và so sánh giữa các mức p không bị nhiễu bởi lần bốc khác nhau.

Thời điểm retire theo vòng đời của dòng hợp lệ (`scenarios.yaml` → `honest_stream`): chứng chỉ của một thiết bị-ngày
được chuyển nhượng với xác suất `transfer_prob`, sau `transfer_delay_days` ngày (lúc 12:00); người nhận retire với
xác suất `retire_prob`, sau thêm `retire_delay_days` ngày.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from rec import config

SALT = 0xA0D1  # tách dòng số ngẫu nhiên của auditor khỏi dòng của generator
DAY_S = 86_400
NOON = 12 * 3600
CHECK_AFTER_S = 2 * DAY_S + NOON  # kiểm lúc 12:00 ngày d + 2, tính từ 00:00 ngày d
REQUEST_AFTER_S = DAY_S + 3600    # yêu cầu MINT lúc 01:00 ngày d + 1


@dataclass(frozen=True)
class Lifecycle:
    transfer_prob: float
    transfer_delay: tuple[int, int]
    retire_prob: float
    retire_delay: tuple[int, int]

    @classmethod
    def from_config(cls) -> Lifecycle:
        h = config.load("scenarios")["honest_stream"]
        return cls(h["transfer_prob"], tuple(h["transfer_delay_days"]), h["retire_prob"], tuple(h["retire_delay_days"]))


class Auditor:
    def __init__(self, seed: int = 0, lifecycle: Lifecycle | None = None):
        self.seed = seed
        self.life = lifecycle or Lifecycle.from_config()

    def _rng(self, key: str) -> np.random.Generator:
        return np.random.default_rng(np.random.SeedSequence([SALT, self.seed, zlib.crc32(key.encode())]))

    @staticmethod
    def resolve(excess_wh_true: int) -> bool:
        """Phân xử lô REVIEW: duyệt khi lô không có phần khai vượt sản lượng thật."""
        return excess_wh_true <= 0

    def draw(self, key: str) -> float:
        """Số u ∈ [0, 1) của lô; lô được kiểm ngẫu nhiên ở mức p khi u < p."""
        return float(self._rng("draw:" + key).random())

    def retired_share(self, key: str, wh: list[int]) -> float:
        """Tỉ lệ Wh của lô đã retire trước lúc kiểm (mỗi phần tử của `wh` là chứng chỉ của một thiết bị)."""
        total = sum(wh)
        if total <= 0:
            return 0.0
        rng, life = self._rng("life:" + key), self.life
        done = 0
        for i, w in enumerate(wh):
            if rng.random() >= life.transfer_prob:
                continue
            t_transfer = REQUEST_AFTER_S + i + int(rng.integers(life.transfer_delay[0], life.transfer_delay[1] + 1)) \
                * DAY_S + NOON
            if rng.random() >= life.retire_prob:
                continue
            t_retire = t_transfer + int(rng.integers(life.retire_delay[0], life.retire_delay[1] + 1)) * DAY_S
            if t_retire <= CHECK_AFTER_S:
                done += w
        return done / total

    def after_check(self, key: str, minted_excess_wh: float, wh: list[int], p: float) -> float:
        """Phần khai vượt còn lọt sau kiểm tra ngẫu nhiên ở mức p."""
        if minted_excess_wh <= 0 or self.draw(key) >= p:
            return minted_excess_wh
        return minted_excess_wh * self.retired_share(key, wh)

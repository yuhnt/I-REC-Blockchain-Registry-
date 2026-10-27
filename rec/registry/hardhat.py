"""Tiến trình `npx hardhat node` chạy nền cho thí nghiệm và demo.

Ngày bắt đầu đặt trước dòng sự kiện (`REC_INITIAL_DATE`), để backend chain đặt timestamp của block theo đồng hồ mô
phỏng (`evm_setNextBlockTimestamp`); E3 bật đào block theo nhịp (`REC_INTERVAL_MS`).
"""
from __future__ import annotations

import os
import socket
import subprocess
import time

from web3 import Web3

from rec import config
from rec.registry.contracts import contracts_dir


class HardhatNode:
    """Tiến trình `npx hardhat node` chạy nền; dừng khi `close()`."""

    def __init__(self, port: int = 8545, initial_date: str = "2021-12-01T00:00:00Z", interval_ms: int | None = None):
        self.port = port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:  # không dùng nhầm một node khác đang chạy
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"cổng {port} đã có tiến trình khác; dừng node cũ (ví dụ rec.deploy.demo --stop)"
                                   " hoặc chọn --port khác")
        env = dict(os.environ, REC_INITIAL_DATE=initial_date)
        if interval_ms:
            env["REC_INTERVAL_MS"] = str(interval_ms)
        log = open(config.resolve_path("artifacts") / f"hardhat_node_{port}.log", "w", encoding="utf-8")
        self.proc = subprocess.Popen(f"npx hardhat node --port {port}", cwd=contracts_dir(), env=env, stdout=log,
                                     stderr=subprocess.STDOUT, shell=True)
        self.url = f"http://127.0.0.1:{port}"
        w3 = Web3(Web3.HTTPProvider(self.url))
        for _ in range(120):
            try:
                if w3.is_connected():
                    return
            except Exception:  # noqa: BLE001 – node chưa lên
                pass
            time.sleep(0.5)
        raise RuntimeError("Hardhat node không khởi động được (xem artifacts/hardhat_node.log)")

    def close(self) -> None:
        if os.name == "nt":
            subprocess.run(f"taskkill /F /T /PID {self.proc.pid}", shell=True, capture_output=True)
        else:
            self.proc.terminate()

"""Backend chain cho mạng công khai (Sepolia): cùng logic với `ChainRegistry`, khác cách ký giao dịch."""
from __future__ import annotations

import time

from web3.exceptions import ContractCustomError, ContractLogicError

from rec.oracles.signer import hardhat_account
from rec.registry.base import Outcome, Plant
from rec.registry.chain_registry import ChainRegistry, _Receipt
from rec.registry.contracts import ROLES


class TestnetRegistry(ChainRegistry):
    """Cùng logic với `ChainRegistry`, nhưng cho mạng công khai (Sepolia qua Alchemy): node không giữ tài khoản, nên
    mọi giao dịch được ký tại máy bằng khóa suy ra từ mnemonic rồi gửi `eth_sendRawTransaction`.

    Không có snapshot hay đặt timestamp: block mang thời gian thật (sau mọi ngày của dòng sự kiện), nên luật "kỳ đã
    kết thúc" luôn qua.
    """

    name = "testnet"

    def __init__(self, plant: Plant, url: str, mnemonic: str, deployment: dict | None = None):
        self._mnemonic = mnemonic
        super().__init__(plant, url, deployment=deployment)

    def _setup_accounts(self) -> None:
        self.mnemonic = self._mnemonic
        self.accounts = {role: hardhat_account(i, self._mnemonic) for i, role in enumerate(ROLES)}
        self.addr = {role: a.address for role, a in self.accounts.items()}
        self.keys = {"verifier": self.accounts["verifier"]}

    def _take_snapshot(self):
        return None

    def checkpoint(self) -> None:
        raise RuntimeError("mạng công khai không có snapshot")

    reset = checkpoint

    def _at(self, t: int) -> None:
        pass  # không đặt được timestamp trên mạng công khai

    def _sign_and_send(self, fn, role: str):
        """Ước lượng gas (revert thì báo lỗi ngay, không tốn phí), ký, gửi, chờ receipt."""
        acct = self.accounts[role]
        tx = fn.build_transaction({"from": acct.address, "nonce": self.w3.eth.get_transaction_count(acct.address,
                                                                                                     "pending")})
        tx["gas"] = int(tx["gas"] * 1.2)
        raw = acct.sign_transaction(tx).raw_transaction
        h = self.w3.eth.send_raw_transaction(raw)
        return self.w3.eth.wait_for_transaction_receipt(h, timeout=600, poll_latency=2)

    def _transact(self, fn, role: str):
        return self._sign_and_send(fn, role)

    def _send(self, fn, role: str, t: int, op: str):
        t_send = time.perf_counter()
        try:
            rcpt = self._sign_and_send(fn, role)
        except (ContractLogicError, ContractCustomError) as e:  # contract revert, phát hiện ngay lúc ước lượng gas
            return None, self._decode_error(str(getattr(e, "data", "")) + " " + str(e))
        # Lỗi khác (không đủ ETH, nonce, mạng) không phải quyết định của contract: để nổi lên, không ghi thành revert.
        self.lat_log.append((op, time.perf_counter() - t_send))
        if rcpt.status == 0:
            return None, "Revert"
        self.gas_log.append((op, rcpt.gasUsed))
        logs = [{"topics": ["0x" + bytes(t).hex() for t in lg.topics], "data": "0x" + bytes(lg.data).hex()}
                for lg in rcpt.logs]
        return _Receipt(rcpt.gasUsed, "0x" + bytes(rcpt.transactionHash).hex(), logs), None

    def operator_edit(self, edit, t):
        fn = self.certs.functions.withdraw(0, self.addr["plant"], 1, "insider")
        _, err = self._send(fn, edit.issuer, t, "operator_edit")
        return Outcome("revert", err or "NoAdminFunction")

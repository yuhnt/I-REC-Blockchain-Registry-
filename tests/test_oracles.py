import dataclasses

import numpy as np
import pytest

from rec.oracles.encoding import data_root
from rec.oracles.node import ACCOUNT_INDEX, oracle_nodes, recover_signer
from rec.oracles.signer import hardhat_account, report_struct
from rec.oracles.store import FileStore
from rec.schema import OracleId

GATE = "0x" + "ab" * 20
CHAIN_ID = 11155111


def _day():
    sun = np.zeros(96, dtype=bool)
    sun[24:72] = True
    series = {OracleId.O1: np.where(sun, 100_000.0, 0.0), OracleId.O2: np.where(sun, 101_700.0, 0.0),
              OracleId.O3: np.where(sun, 150.0, 0.0), OracleId.O4: np.where(sun, 160.0, 0.0)}
    series[OracleId.O2][30] = np.nan  # một slot thiếu
    return series, sun


def test_four_nodes_have_four_distinct_keys(tmp_path):
    nodes = oracle_nodes("CP-1", GATE, CHAIN_ID, store=FileStore(tmp_path))
    assert [n.oracle for n in nodes.values()] == list(OracleId)
    addrs = {n.address for n in nodes.values()}
    assert len(addrs) == 4
    for o, n in nodes.items():
        assert n.address == hardhat_account(ACCOUNT_INDEX[o]).address


def test_each_node_reads_its_own_source_stores_and_signs(tmp_path):
    store = FileStore(tmp_path)
    nodes = oracle_nodes("CP-1", GATE, CHAIN_ID, store=store)
    series, sun = _day()
    for o, node in nodes.items():
        rep = node.observe(19000, series[o], sun)
        assert rep.oracle is o and rep.data_root == data_root(series[o])
        assert store.verify(rep.data_root)                                   # chuỗi 15 phút nằm trong kho, khớp hash
        assert recover_signer(rep, GATE, CHAIN_ID) == node.address           # chữ ký của đúng nút này
    o2 = nodes[OracleId.O2].observe(19000, series[OracleId.O2], sun)
    assert o2.slots_present == 47                                             # slot thiếu không bị điền 0


def test_node_cannot_sign_for_another_oracle(tmp_path):
    nodes = oracle_nodes("CP-1", GATE, CHAIN_ID)
    series, sun = _day()
    o2_report = nodes[OracleId.O2].observe(19000, series[OracleId.O2], sun)
    with pytest.raises(ValueError):
        nodes[OracleId.O1].sign(o2_report)
    # Dù có ép ký, chữ ký của khóa O1 trên báo cáo O2 không khớp địa chỉ O2 mà contract chấp nhận.
    o1 = nodes[OracleId.O1]
    forged = dataclasses.replace(o2_report, signature=o1.signer.sign(o1.account, "OracleReport",
                                                                     report_struct(o2_report)))
    assert recover_signer(forged, GATE, CHAIN_ID) != nodes[OracleId.O2].address


def test_tampered_report_no_longer_matches_signer(tmp_path):
    node = oracle_nodes("CP-1", GATE, CHAIN_ID)[OracleId.O1]
    series, sun = _day()
    rep = node.observe(19000, series[OracleId.O1], sun)
    tampered = dataclasses.replace(rep, wh_day=rep.wh_day * 2)               # khai tăng sau khi đã ký
    assert recover_signer(tampered, GATE, CHAIN_ID) != node.address
    other_chain = recover_signer(rep, GATE, 31337)                            # domain EIP-712 gắn với chainId
    assert other_chain != node.address

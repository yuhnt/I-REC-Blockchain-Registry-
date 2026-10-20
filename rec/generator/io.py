"""Đọc / ghi dòng sự kiện (JSONL) và nhãn ẩn (parquet) của generator.

Mỗi dòng JSONL là một sự kiện: {"t": ..., "kind": ..., "payload": {...}}. Enum ghi bằng giá trị,
bytes ghi bằng hex có tiền tố 0x.
"""
from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Iterator
from enum import Enum
from pathlib import Path

import pandas as pd

from rec.schema import PAYLOAD_TYPES, EditAction, Event, EventKind, Label, OracleId

_ENUM_FIELDS = {"oracle": OracleId, "action": EditAction}


def _plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, tuple):
        return list(value)
    return value


def event_to_dict(e: Event) -> dict:
    payload = {f.name: _plain(getattr(e.payload, f.name)) for f in dataclasses.fields(e.payload)}
    return {"t": e.t, "kind": e.kind.value, "payload": payload}


def event_from_dict(d: dict) -> Event:
    kind = EventKind(d["kind"])
    cls = PAYLOAD_TYPES[kind]
    fields = {}
    for f in dataclasses.fields(cls):
        if f.name not in d["payload"]:
            continue
        v = d["payload"][f.name]
        if f.name in _ENUM_FIELDS:
            v = _ENUM_FIELDS[f.name](v)
        elif isinstance(v, str) and v.startswith("0x") and f.name in ("data_root", "signature"):
            v = bytes.fromhex(v[2:])
        elif isinstance(v, list):
            v = tuple(v)
        fields[f.name] = v
    return Event(d["t"], kind, cls(**fields))


def write_events(path: Path, events: Iterable[Event]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for e in events:
            f.write(json.dumps(event_to_dict(e), ensure_ascii=False, separators=(",", ":")) + "\n")
            n += 1
    return n


def read_events(path: Path) -> Iterator[Event]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield event_from_dict(json.loads(line))


def labels_frame(labels: Iterable[Label], stream: str) -> pd.DataFrame:
    rows = [{"stream": stream, "id": lb.req_id, "scenario": lb.scenario, "kind": lb.kind.value,
             "excess_wh_true": lb.excess_wh_true} for lb in labels]
    return pd.DataFrame(rows, columns=["stream", "id", "scenario", "kind", "excess_wh_true"])

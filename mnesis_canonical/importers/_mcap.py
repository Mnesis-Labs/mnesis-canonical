"""Minimal, pure-stdlib MCAP reader/writer (record subset).

This is *not* a full MCAP implementation — it supports exactly the record types
the airbot-mcap smoke path needs: the file magic, ``Header``, ``Schema``,
``Channel``, ``Message`` and ``Footer`` records, laid out per the MCAP spec
(https://mcap.dev/spec). Message payloads are carried opaquely as bytes, so a
channel may declare any ``message_encoding`` (the smoke fixture uses ``json``).

Real airbot_ie/AIRDC logs encode their messages as FlatBuffers; decoding those
is a documented follow-up (see docs/RELEASE_CHECKLIST_v1.0.md). This subset lets
the importer exercise a genuine MCAP container end-to-end without third-party
dependencies or third-party data.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"\x89MCAP0\r\n"

# Record opcodes (MCAP spec §Records).
_OP_HEADER = 0x01
_OP_FOOTER = 0x02
_OP_SCHEMA = 0x03
_OP_CHANNEL = 0x04
_OP_MESSAGE = 0x05


def _prefixed_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<I", len(b)) + b


def _prefixed_bytes(b: bytes) -> bytes:
    return struct.pack("<I", len(b)) + b


def _record(opcode: int, body: bytes) -> bytes:
    return struct.pack("<BQ", opcode, len(body)) + body


@dataclass(frozen=True)
class Channel:
    id: int
    topic: str
    message_encoding: str


@dataclass(frozen=True)
class Message:
    channel: Channel
    sequence: int
    log_time: int
    publish_time: int
    data: bytes


def write_messages(
    path: str | Path,
    messages: list[dict],
    *,
    topic: str,
    message_encoding: str = "json",
    profile: str = "",
    library: str = "mnesis-canonical/importers",
) -> Path:
    """Write ``messages`` (each ``{"log_time": int, "data": bytes}``) as a single
    MCAP channel. Returns the written path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    header = _record(_OP_HEADER, _prefixed_str(profile) + _prefixed_str(library))
    # One schema + channel for the whole file.
    schema = _record(
        _OP_SCHEMA,
        struct.pack("<H", 1)
        + _prefixed_str(topic)
        + _prefixed_str(message_encoding)
        + _prefixed_bytes(b""),
    )
    channel = _record(
        _OP_CHANNEL,
        struct.pack("<HH", 1, 1)
        + _prefixed_str(topic)
        + _prefixed_str(message_encoding)
        + struct.pack("<I", 0),  # empty metadata map
    )

    with open(p, "wb") as f:
        f.write(MAGIC)
        f.write(header)
        f.write(schema)
        f.write(channel)
        for seq, msg in enumerate(messages):
            log_time = int(msg["log_time"])
            body = (
                struct.pack("<HIQQ", 1, seq, log_time, log_time) + msg["data"]
            )
            f.write(_record(_OP_MESSAGE, body))
        # Footer with zeroed summary offsets (no summary section).
        f.write(_record(_OP_FOOTER, struct.pack("<QQI", 0, 0, 0)))
        f.write(MAGIC)
    return p


def read_messages(path: str | Path) -> list[Message]:
    """Read all ``Message`` records from an MCAP file (subset reader).

    Raises ValueError if the file magic is missing/corrupt.
    """
    raw = Path(path).read_bytes()
    if raw[:8] != MAGIC:
        raise ValueError("not an MCAP file (bad leading magic)")
    if raw[-8:] != MAGIC:
        raise ValueError("truncated MCAP file (bad trailing magic)")

    channels: dict[int, Channel] = {}
    messages: list[Message] = []
    off = 8
    end = len(raw) - 8
    while off < end:
        opcode, length = struct.unpack_from("<BQ", raw, off)
        off += 9
        body = raw[off : off + length]
        off += length
        if opcode == _OP_CHANNEL:
            cid, _schema_id = struct.unpack_from("<HH", body, 0)
            pos = 4
            topic, pos = _read_prefixed_str(body, pos)
            encoding, pos = _read_prefixed_str(body, pos)
            channels[cid] = Channel(id=cid, topic=topic, message_encoding=encoding)
        elif opcode == _OP_MESSAGE:
            cid, seq, log_time, publish_time = struct.unpack_from("<HIQQ", body, 0)
            data = body[struct.calcsize("<HIQQ") :]
            ch = channels.get(cid, Channel(id=cid, topic="", message_encoding=""))
            messages.append(
                Message(
                    channel=ch,
                    sequence=seq,
                    log_time=log_time,
                    publish_time=publish_time,
                    data=data,
                )
            )
        # Header / Schema / Footer are skipped by this subset reader.
    return messages


def _read_prefixed_str(buf: bytes, pos: int) -> tuple[str, int]:
    (n,) = struct.unpack_from("<I", buf, pos)
    pos += 4
    s = buf[pos : pos + n].decode("utf-8")
    return s, pos + n

from __future__ import annotations

import json
import socket
from typing import Any


def send_request(
    host: str,
    port: int,
    payload: dict[str, Any],
    timeout: float = 2.0,
) -> dict[str, Any]:
    data = (json.dumps(payload) + "\n").encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(data)
        response = _recv_line(sock)
    parsed: dict[str, Any] = json.loads(response)
    return parsed


def _recv_line(sock: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    raw = b"".join(chunks)
    return raw.split(b"\n", 1)[0].decode("utf-8")

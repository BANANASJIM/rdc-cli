from __future__ import annotations

import json
import socket
from typing import Any

from rdc._transport import recv_line as _recv_line


def send_request(
    host: str,
    port: int,
    payload: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    data = (json.dumps(payload) + "\n").encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(data)
        response = _recv_line(sock)
    parsed: dict[str, Any] = json.loads(response)
    return parsed

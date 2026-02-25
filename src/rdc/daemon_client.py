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


def send_request_binary(
    host: str,
    port: int,
    payload: dict[str, Any],
    timeout: float = 30.0,
) -> tuple[dict[str, Any], bytes | None]:
    """Send JSON-RPC request and return (response_dict, binary_data | None).

    Uses a buffered reader to avoid losing bytes past the JSON newline.
    """
    data = (json.dumps(payload) + "\n").encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(data)
        f = sock.makefile("rb")
        line = f.readline()
        if not line:
            raise OSError("empty response from daemon")
        parsed: dict[str, Any] = json.loads(line.rstrip(b"\n").decode("utf-8"))
        binary_size = parsed.get("result", {}).get("_binary_size")
        if binary_size is not None:
            binary_size = int(binary_size)
            if binary_size < 0:
                raise ValueError("invalid _binary_size: must be >= 0")
            if binary_size == 0:
                return parsed, b""
            chunks: list[bytes] = []
            remaining = binary_size
            while remaining > 0:
                chunk = f.read(min(remaining, 65536))
                if not chunk:
                    raise OSError("connection closed before all binary data received")
                chunks.append(chunk)
                remaining -= len(chunk)
            return parsed, b"".join(chunks)
        return parsed, None

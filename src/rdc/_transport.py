"""Shared TCP transport helpers for daemon client and server."""

from __future__ import annotations

import socket


def recv_line(sock: socket.socket, max_bytes: int = 10 * 1024 * 1024) -> str:
    """Read one newline-terminated line from a socket.

    Args:
        sock: Connected socket to read from.
        max_bytes: Upper bound on total bytes before raising ValueError.

    Returns:
        Decoded line (without trailing newline), or empty string on EOF.

    Raises:
        ValueError: If accumulated data exceeds *max_bytes*.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("recv_line: message exceeds max_bytes limit")
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        return ""
    return b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")

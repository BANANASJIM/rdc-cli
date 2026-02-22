"""Shared TCP transport helpers for daemon client and server."""

from __future__ import annotations

import socket


def recv_line(sock: socket.socket) -> str:
    """Read one newline-terminated line from a socket.

    Returns:
        Decoded line (without trailing newline), or empty string on EOF.
    """
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        return ""
    return b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")

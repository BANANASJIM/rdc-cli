from __future__ import annotations

import argparse
import json
import socket
from dataclasses import dataclass
from typing import Any


@dataclass
class DaemonState:
    capture: str
    current_eid: int
    token: str


def run_server(host: str, port: int, state: DaemonState) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(32)

        running = True
        while running:
            conn, _addr = server.accept()
            with conn:
                line = _recv_line(conn)
                if not line:
                    continue
                request = json.loads(line)
                response, running = _handle_request(request, state)
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))


def _recv_line(conn: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    if not chunks:
        return ""
    return b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")


def _handle_request(request: dict[str, Any], state: DaemonState) -> tuple[dict[str, Any], bool]:
    request_id = request.get("id", 0)
    params = request.get("params") or {}
    token = params.get("_token")
    if token != state.token:
        return _error_response(request_id, -32600, "invalid token"), True

    method = request.get("method")
    if method == "ping":
        return _result_response(request_id, {"ok": True}), True
    if method == "status":
        return _result_response(
            request_id,
            {"capture": state.capture, "current_eid": state.current_eid},
        ), True
    if method == "goto":
        eid = int(params.get("eid", 0))
        state.current_eid = eid
        return _result_response(request_id, {"current_eid": state.current_eid}), True
    if method == "shutdown":
        return _result_response(request_id, {"ok": True}), False

    return _error_response(request_id, -32601, "method not found"), True


def _result_response(request_id: int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: int, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        state=DaemonState(capture=args.capture, current_eid=0, token=args.token),
    )


if __name__ == "__main__":
    main()

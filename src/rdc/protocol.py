from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonRpcRequest:
    jsonrpc: str
    method: str
    id: int
    params: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "id": self.id,
        }
        if self.params is not None:
            payload["params"] = self.params
        return payload


def _request(method: str, request_id: int, params: dict[str, Any] | None = None) -> JsonRpcRequest:
    if request_id < 0:
        raise ValueError("request id must be >= 0")
    return JsonRpcRequest(jsonrpc="2.0", method=method, id=request_id, params=params)


def ping_request(request_id: int = 1) -> dict[str, Any]:
    return _request("ping", request_id).to_dict()


def shutdown_request(request_id: int = 1) -> dict[str, Any]:
    return _request("shutdown", request_id).to_dict()

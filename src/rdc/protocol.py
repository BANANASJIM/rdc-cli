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


def ping_request(token: str, request_id: int = 1) -> dict[str, Any]:
    return _request("ping", request_id, {"_token": token}).to_dict()


def status_request(token: str, request_id: int = 1) -> dict[str, Any]:
    return _request("status", request_id, {"_token": token}).to_dict()


def goto_request(token: str, eid: int, request_id: int = 1) -> dict[str, Any]:
    return _request("goto", request_id, {"_token": token, "eid": eid}).to_dict()


def shutdown_request(token: str, request_id: int = 1) -> dict[str, Any]:
    return _request("shutdown", request_id, {"_token": token}).to_dict()


def count_request(
    token: str,
    what: str,
    *,
    pass_name: str | None = None,
    request_id: int = 1,
) -> dict[str, Any]:
    params: dict[str, Any] = {"_token": token, "what": what}
    if pass_name is not None:
        params["pass"] = pass_name
    return _request("count", request_id, params).to_dict()


def shader_map_request(token: str, request_id: int = 1) -> dict[str, Any]:
    return _request("shader_map", request_id, {"_token": token}).to_dict()

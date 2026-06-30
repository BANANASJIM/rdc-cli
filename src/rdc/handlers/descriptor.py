"""Descriptor handlers: descriptors, usage, usage_all, counter_list, counter_fetch."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rdc.handlers._helpers import (
    PipeError,
    _enum_name,
    _error_response,
    _result_response,
    require_pipe,
)
from rdc.handlers._types import Handler

if TYPE_CHECKING:
    from rdc.daemon_server import DaemonState


def _bind_bucket(items: Any) -> dict[int, tuple[str, int]]:
    return {
        getattr(r, "fixedBindNumber", 0): (r.name, getattr(r, "fixedBindSetOrSpace", 0))
        for r in items
    }


def _reflection_binding_maps(pipe_state: Any) -> dict[int, dict[str, dict[int, tuple[str, int]]]]:
    """Per-stage {bucket: {bind_number: (name, set)}} from reflection, keyed by stage value."""
    from rdc.services.query_service import STAGE_MAP

    maps: dict[int, dict[str, dict[int, tuple[str, int]]]] = {}
    for stage_val in STAGE_MAP.values():
        refl = pipe_state.GetShaderReflection(stage_val)
        if refl is None:
            continue
        maps[stage_val] = {
            "ro": _bind_bucket(getattr(refl, "readOnlyResources", [])),
            "rw": _bind_bucket(getattr(refl, "readWriteResources", [])),
            "cb": _bind_bucket(getattr(refl, "constantBlocks", [])),
        }
    return maps


def _descriptor_locations(state: DaemonState, used: Any) -> dict[int, Any]:
    """Map id(access) -> logical location via GetDescriptorLocations, batched per store."""
    assert state.adapter is not None
    get_locs = getattr(state.adapter.controller, "GetDescriptorLocations", None)
    if get_locs is None or not hasattr(state.rd, "DescriptorRange"):
        return {}
    by_store: dict[Any, list[Any]] = {}
    for ud in used:
        by_store.setdefault(ud.access.descriptorStore, []).append(ud.access)
    out: dict[int, Any] = {}
    for store, accesses in by_store.items():
        try:
            locs = get_locs(store, [state.rd.DescriptorRange(a) for a in accesses])
        except Exception:  # noqa: BLE001
            continue
        for access, loc in zip(accesses, locs, strict=False):
            out[id(access)] = loc
    return out


def _refl_bucket(type_name: str) -> str:
    if type_name == "ConstantBuffer":
        return "cb"
    if type_name.startswith("ReadWrite"):
        return "rw"
    return "ro"


def _handle_descriptors(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    try:
        eid, pipe_state = require_pipe(params, state, request_id)
    except PipeError as exc:
        return exc.response, True
    if not hasattr(pipe_state, "GetAllUsedDescriptors"):
        return _error_response(request_id, -32002, "GetAllUsedDescriptors not available"), True
    used = pipe_state.GetAllUsedDescriptors(True)
    bind_maps = _reflection_binding_maps(pipe_state)
    loc_map = _descriptor_locations(state, used)
    desc_rows: list[dict[str, Any]] = []
    for ud in used:
        acc = ud.access
        desc = ud.descriptor
        stage_name = _enum_name(acc.stage)
        type_name = _enum_name(acc.type)
        fmt = getattr(desc, "format", None)
        fmt_name = fmt.Name() if fmt and hasattr(fmt, "Name") else str(fmt) if fmt else ""
        res_id = int(desc.resource)
        d_row: dict[str, Any] = {
            "stage": stage_name,
            "type": type_name,
            "index": acc.index,
            "array_element": acc.arrayElement,
            "resource_id": res_id,
            "format": fmt_name,
            "byte_size": getattr(desc, "byteSize", 0),
        }
        loc = loc_map.get(id(acc))
        logical = getattr(loc, "logicalBindName", "") if loc is not None else ""
        bind_num = getattr(loc, "fixedBindNumber", None) if loc is not None else None
        name, bset = "", None
        stage_buckets = bind_maps.get(int(acc.stage))
        if stage_buckets is not None and bind_num is not None:
            name, bset = stage_buckets[_refl_bucket(type_name)].get(bind_num, ("", None))
        d_row["binding"] = name or logical
        d_row["set"] = bset if bset is not None else acc.index
        d_row["resource_name"] = state.res_names.get(res_id, "")
        tex = state.tex_map.get(res_id)
        if tex is not None:
            d_row["width"] = tex.width
            d_row["height"] = tex.height
        if type_name in ("Sampler", "ImageSampler"):
            s = getattr(ud, "sampler", None)
            if s is not None:
                au = getattr(s, "addressU", "")
                av = getattr(s, "addressV", "")
                aw = getattr(s, "addressW", "")
                cf = getattr(s, "compareFunction", "")
                d_row["sampler"] = {
                    "address_u": _enum_name(au),
                    "address_v": _enum_name(av),
                    "address_w": _enum_name(aw),
                    "filter": _enum_name(getattr(s, "filter", "")),
                    "compare_function": _enum_name(cf),
                    "min_lod": float(getattr(s, "minLOD", 0.0)),
                    "max_lod": float(getattr(s, "maxLOD", 0.0)),
                    "mip_bias": float(getattr(s, "mipBias", 0.0)),
                    "max_anisotropy": float(getattr(s, "maxAnisotropy", 0)),
                }
        desc_rows.append(d_row)
    return _result_response(request_id, {"eid": eid, "descriptors": desc_rows}), True


def _handle_usage(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    resid = int(params.get("id", 0))
    if resid not in state.res_names:
        return _error_response(request_id, -32001, f"resource {resid} not found"), True
    rid_obj = state.res_rid_map[resid]
    usage_list = state.adapter.controller.GetUsage(rid_obj.resourceId)
    entries = [{"eid": u.eventId, "usage": _enum_name(u.usage)} for u in usage_list]
    result_data: dict[str, Any] = {"id": resid, "entries": entries}
    if params.get("resolve_names", True):
        result_data["name"] = state.res_names.get(resid, "")
    return _result_response(request_id, result_data), True


def _handle_usage_all(
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    type_filter = params.get("type")
    usage_filter = params.get("usage")
    usage_rows: list[dict[str, Any]] = []
    for resid, name in state.res_names.items():
        if type_filter and state.res_types.get(resid, "") != type_filter:
            continue
        rid_obj = state.res_rid_map.get(resid)
        if rid_obj is None:
            continue
        usage_list = state.adapter.controller.GetUsage(rid_obj.resourceId)
        for u in usage_list:
            uname = _enum_name(u.usage)
            if usage_filter and uname != usage_filter:
                continue
            usage_rows.append({"id": resid, "name": name, "eid": u.eventId, "usage": uname})
    usage_rows.sort(key=lambda r: (r["id"], r["eid"]))
    return _result_response(request_id, {"rows": usage_rows, "total": len(usage_rows)}), True


def _handle_counter_list(  # noqa: PLR0912
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    controller = state.adapter.controller
    raw_counters = controller.EnumerateCounters()
    counters_out = []
    for c in raw_counters:
        try:
            desc = controller.DescribeCounter(c)
        except Exception:  # noqa: BLE001
            continue
        if not desc.name or desc.name.startswith("ERROR"):
            continue
        cat = desc.category
        cat_str = _enum_name(cat)
        counters_out.append(
            {
                "id": int(c),
                "name": desc.name,
                "category": cat_str,
                "description": desc.description,
                "unit": _enum_name(desc.unit),
                "type": _enum_name(desc.resultType),
                "byte_width": desc.resultByteWidth,
                "uuid": str(getattr(desc, "uuid", "") or ""),
            }
        )
    return (
        _result_response(request_id, {"counters": counters_out, "total": len(counters_out)}),
        True,
    )


def _handle_counter_fetch(  # noqa: PLR0912
    request_id: int, params: dict[str, Any], state: DaemonState
) -> tuple[dict[str, Any], bool]:
    assert state.adapter is not None
    controller = state.adapter.controller
    raw_counters = controller.EnumerateCounters()
    counter_info: dict[int, dict[str, Any]] = {}
    for c in raw_counters:
        try:
            desc = controller.DescribeCounter(c)
        except Exception:  # noqa: BLE001
            continue
        if not desc.name or desc.name.startswith("ERROR"):
            continue
        counter_info[int(c)] = {
            "name": desc.name,
            "unit": _enum_name(desc.unit),
            "result_type": desc.resultType,
            "byte_width": desc.resultByteWidth,
        }
    name_filter = params.get("name")
    if name_filter:
        name_lower = str(name_filter).lower()
        counter_info = {k: v for k, v in counter_info.items() if name_lower in v["name"].lower()}
    if not counter_info:
        return _result_response(request_id, {"rows": [], "total": 0}), True
    fetch_counter_objs = [c for c in raw_counters if int(c) in counter_info]
    results = controller.FetchCounters(fetch_counter_objs)
    eid_filter = params.get("eid")
    if eid_filter is not None:
        try:
            eid_filter = int(eid_filter)
        except (TypeError, ValueError):
            return _error_response(request_id, -32602, "eid must be an integer"), True
    fetch_rows: list[dict[str, Any]] = []
    for r in results:
        if eid_filter is not None and r.eventId != eid_filter:
            continue
        cid = int(r.counter)
        info = counter_info.get(cid)
        if info is None:
            continue
        rt = info["result_type"]
        bw = info["byte_width"]
        rt_name = _enum_name(rt)
        if rt_name == "Float":
            val: int | float = r.value.f if bw == 4 else r.value.d
        elif rt_name in ("UInt", "UNorm"):
            val = r.value.u32 if bw == 4 else r.value.u64
        else:
            val = r.value.u32 if bw == 4 else r.value.u64
        fetch_rows.append(
            {
                "eid": r.eventId,
                "counter": info["name"],
                "value": val,
                "unit": info["unit"],
            }
        )
    fetch_rows.sort(key=lambda row: (row["eid"], row["counter"]))
    return _result_response(request_id, {"rows": fetch_rows, "total": len(fetch_rows)}), True


HANDLERS: dict[str, Handler] = {
    "descriptors": _handle_descriptors,
    "usage": _handle_usage,
    "usage_all": _handle_usage_all,
    "counter_list": _handle_counter_list,
    "counter_fetch": _handle_counter_fetch,
}

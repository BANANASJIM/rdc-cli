# Phase 4C-1: Mesh Export — Test Plan

## Handler Tests (`tests/unit/test_mesh_handler.py`)

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_mesh_data_triangle_list` | 3 vertices decoded, topology=TriangleList |
| 2 | `test_mesh_data_indexed` | index buffer decoded, indices=[0,2,1] |
| 3 | `test_mesh_data_gs_out` | stage=gs-out forwarded correctly |
| 4 | `test_mesh_data_default_stage` | stage defaults to vs-out |
| 5 | `test_mesh_data_no_postvs` | vertexResourceId=0 → -32001 |
| 6 | `test_mesh_data_no_adapter` | no adapter → -32002 |
| 7 | `test_mesh_data_uses_current_eid` | omit eid → uses state.current_eid |

## CLI Tests (`tests/unit/test_mesh_commands.py`)

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_mesh_default_obj` | stdout contains `v` and `f` lines |
| 2 | `test_mesh_json_output` | --json returns valid JSON with all fields |
| 3 | `test_mesh_file_output` | -o writes file, stderr has summary |
| 4 | `test_mesh_no_header` | --no-header suppresses # comment |
| 5 | `test_mesh_stage_forwarded` | --stage gs-out in daemon params |
| 6 | `test_mesh_help` | --help shows EID, --stage, -o |
| 7 | `test_mesh_in_main_help` | rdc --help lists mesh |
| 8 | `test_obj_triangle_list_faces` | f lines correct for TriangleList |
| 9 | `test_obj_triangle_strip_faces` | alternating winding |
| 10 | `test_obj_triangle_fan_faces` | pivot vertex 0 |
| 11 | `test_obj_point_list_no_faces` | no f lines for PointList |
| 12 | `test_obj_1_indexed` | f indices start at 1 |
| 13 | `test_obj_indexed_mesh` | uses index buffer for faces |

## GPU Integration Tests (`tests/integration/test_daemon_handlers_real.py`)

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_mesh_data_real` | non-zero vertices returned |
| 2 | `test_mesh_data_vertex_count` | vertex_count == len(vertices) |
| 3 | `test_mesh_data_topology_string` | topology is str, not int |

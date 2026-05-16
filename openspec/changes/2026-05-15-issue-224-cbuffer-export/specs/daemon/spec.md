## ADDED Requirements

### Requirement: Constant Buffer Raw Export
The daemon SHALL expose a handler to export raw constant-buffer bytes to a temporary file.

#### Scenario: Export buffer-backed constant buffer
- **WHEN** client requests `cbuffer_raw` with `eid`, `set`, `binding`, and `stage`
- **THEN** daemon resolves the constant block via `fixedBindSetOrSpace` / `fixedBindNumber`,
  calls `GetBufferData(resource, byteOffset, byteSize)`, writes bytes to
  `state.temp_dir/cbuffer_<eid>_<set>_<binding>.bin`, and returns `{"path", "size"}`.
- **IF** `state.adapter` is None, return error -32002.
- **IF** `eid` is not a valid draw event, return error.

#### Scenario: Reject non-buffer-backed constant buffer
- **WHEN** client requests `cbuffer_raw` and `ConstantBlock.bufferBacked == False`
- **THEN** daemon returns a JSON-RPC error with a message indicating the cbuffer is not
  buffer-backed (push constant or root constant) and does not write any file.

#### Scenario: RenderDoc version guard
- **WHEN** `GetConstantBlock` is not present on the pipeline state object
- **THEN** daemon returns an error indicating the API is unavailable on this RenderDoc version.

### Requirement: Constant Buffer CLI Command
The CLI SHALL expose `rdc cbuffer` as a first-class command for decoded and raw export.

#### Scenario: Decoded JSON output
- **WHEN** user runs `rdc cbuffer [EID] --stage STAGE --set N --binding N`
- **THEN** CLI calls `cbuffer_decode` handler and writes the JSON response to stdout.
- **IF** `EID` is omitted, CLI resolves it via `complete_eid`.

#### Scenario: Raw binary export
- **WHEN** user runs `rdc cbuffer [EID] --raw -o FILE`
- **THEN** CLI resolves the VFS path `/draws/<eid>/cbuffer/<set>/<binding>/data` via
  `_export_vfs_path` (vfs_ls + resolve_path → _deliver_binary), exactly mirroring how
  `rdc buffer --raw` uses `/buffers/<id>/data`, and writes bytes to `FILE`.
- **IF** `-o` is not specified alongside `--raw`, CLI exits with a usage error.

#### Scenario: No active session
- **WHEN** user runs `rdc cbuffer` and no daemon session is active
- **THEN** CLI exits with code 1 and prints an error message to stderr.

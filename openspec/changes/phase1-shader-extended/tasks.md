# Tasks: phase1-shader-extended

## Implementation Tasks

### Phase 1: CLI Layer
- [ ] 1.1 Add Click options to `rdc shader` command:
  - `--reflect` (flag)
  - `--constants` (flag)
  - `--source` (flag)
  - `--target` (option, requires arg)
  - `--targets` (flag)
  - `-o/--output` (option, requires path)
  - `--all` (flag)
- [ ] 1.2 Add new command `rdc shaders` with options:
  - `--stage` (option)
  - `--sort` (option)
- [ ] 1.3 Add new command `rdc pipeline` with options:
  - `eid` (argument)
  - `section` (argument, optional)
- [ ] 1.4 Add new command `rdc bindings` with options:
  - `eid` (argument)
  - `--binding` (option)
- [ ] 1.5 Update CLI handler to pass new options to daemon

### Phase 2: Daemon Layer
- [ ] 2.1 Add JSON-RPC handlers:
  - `shader_targets`: list available formats
  - `shader_reflect`: get input/output/cbuffers
  - `shader_constants`: get constant buffer values
  - `shader_source`: get debug source
  - `shader_disasm`: get disassembly with format
  - `shader_all`: get all stages
  - `shaders`: list all unique shaders
  - `pipeline`: get pipeline state
  - `bindings`: get descriptor bindings
- [ ] 2.2 Wire handlers in daemon_server.py

### Phase 3: Query Service
- [ ] 3.1 Implement `get_disassembly_targets()` helper
- [ ] 3.2 Implement `get_shader_reflection()` helper
- [ ] 3.3 Implement `get_constant_buffer_values()` helper
- [ ] 3.4 Implement `get_shader_source()` helper with fallback
- [ ] 3.5 Implement `get_all_shaders()` helper
- [ ] 3.6 Implement `get_pipeline_state()` helper
- [ ] 3.7 Implement `get_bindings()` helper
- [ ] 3.8 Add file export helpers

### Phase 4: Testing
- [ ] 4.1 Write unit tests for query_service helpers
- [ ] 4.2 Add mock tests for new daemon handlers
- [ ] 4.3 Test CLI option parsing
- [ ] 4.4 Run `make check` - must pass with 80%+ coverage

### Phase 5: Integration
- [ ] 5.1 Test with real capture file if available
- [ ] 5.2 Verify output format matches design doc examples
- [ ] 5.3 Create PR and merge

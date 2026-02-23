# VFS -- Virtual File System

`rdc` exposes capture data through a virtual filesystem (VFS) that maps
RenderDoc internal structures to familiar path-based navigation.

## Path namespace

All VFS paths follow the scheme:

```
rdc://<session>/<path>
```

When using the default session, paths start from the root `/`:

```bash
rdc ls /                          # list top-level VFS entries
rdc ls /textures                  # list textures
rdc cat /events/142               # show event details
rdc tree /pipeline/142            # tree view of pipeline state
```

## VFS commands

| Command | Description |
|---------|-------------|
| `rdc ls [path]` | List entries at a VFS path |
| `rdc cat <path>` | Display content of a VFS node |
| `rdc tree [path]` | Tree view of a VFS subtree |

### Options

```bash
rdc ls -l /textures               # long format (TSV with metadata)
rdc ls -F /                       # append type indicators (/ * @)
rdc ls --json /textures           # JSON output
rdc tree --depth 2 /              # limit tree depth
```

## Path structure

The VFS root contains top-level categories that map to RenderDoc data:

```
/
├── events/          # all events (actions, draws, dispatches)
├── textures/        # texture resources
├── buffers/         # buffer resources
├── pipeline/        # pipeline state per EID
└── shaders/         # shader resources
+-- ...
```

## Examples

Browse the capture interactively:

```bash
rdc open capture.rdc
rdc tree --depth 1 /              # overview
rdc ls /textures                  # list all textures
rdc cat /events/142               # event details as text
rdc ls --json /pipeline/142       # pipeline state as JSON
```

Pipe VFS output into other tools:

```bash
rdc ls -l /textures | sort -k2    # sort textures
rdc tree / | grep -i "shader"     # find shader nodes
```

"""rdc mesh -- export post-transform mesh as OBJ."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from rdc.commands._helpers import call
from rdc.formatters.json_fmt import write_json


@click.command("mesh")
@click.argument("eid", type=int, required=False, default=None)
@click.option(
    "--stage",
    type=click.Choice(["vs-out", "gs-out"]),
    default="vs-out",
    help="Mesh data stage (default: vs-out)",
)
@click.option("-o", "--output", type=click.Path(), default=None, help="Write to file")
@click.option("--json", "use_json", is_flag=True, help="JSON output")
@click.option("--no-header", is_flag=True, help="Suppress OBJ header comment")
def mesh_cmd(
    eid: int | None,
    stage: str,
    output: str | None,
    use_json: bool,
    no_header: bool,
) -> None:
    """Export post-transform mesh as OBJ."""
    params: dict[str, Any] = {"stage": stage}
    if eid is not None:
        params["eid"] = eid

    result = call("mesh_data", params)

    if use_json:
        faces = _generate_faces(result["vertex_count"], result["indices"], result["topology"])
        result["faces"] = faces
        result["face_count"] = len(faces)
        write_json(result)
        return

    positions = _extract_positions(result["vertices"])
    faces = _generate_faces(result["vertex_count"], result["indices"], result["topology"])
    obj_text = _format_obj(
        positions,
        faces,
        eid=result["eid"],
        stage=result["stage"],
        topology=result["topology"],
        no_header=no_header,
    )

    if output:
        Path(output).write_text(obj_text)
        click.echo(f"mesh: {len(positions)} vertices, {len(faces)} faces -> {output}", err=True)
    else:
        click.echo(obj_text, nl=False)


def _extract_positions(vertices: list[list[float]]) -> list[tuple[float, float, float]]:
    """Extract xyz from vertex data (no perspective divide)."""
    positions = []
    for v in vertices:
        x = v[0] if len(v) > 0 else 0.0
        y = v[1] if len(v) > 1 else 0.0
        z = v[2] if len(v) > 2 else 0.0
        positions.append((x, y, z))
    return positions


def _generate_faces(vertex_count: int, indices: list[int], topology: str) -> list[list[int]]:
    """Generate triangle faces from topology. Returns 0-indexed triples."""
    idx = indices if indices else list(range(vertex_count))
    n = len(idx)
    faces: list[list[int]] = []
    match topology:
        case "TriangleList":
            for i in range(0, n - 2, 3):
                faces.append([idx[i], idx[i + 1], idx[i + 2]])
        case "TriangleStrip":
            for i in range(n - 2):
                if i % 2 == 0:
                    faces.append([idx[i], idx[i + 1], idx[i + 2]])
                else:
                    faces.append([idx[i + 1], idx[i], idx[i + 2]])
        case "TriangleFan":
            for i in range(1, n - 1):
                faces.append([idx[0], idx[i], idx[i + 1]])
        case _:
            pass
    return faces


def _format_obj(
    positions: list[tuple[float, float, float]],
    faces: list[list[int]],
    *,
    eid: int,
    stage: str,
    topology: str,
    no_header: bool = False,
) -> str:
    """Format vertex positions and faces as OBJ text."""
    lines: list[str] = []
    if not no_header:
        lines.append(
            f"# rdc mesh export: eid={eid} stage={stage} "
            f"vertices={len(positions)} faces={len(faces)} "
            f"topology={topology}"
        )
    for x, y, z in positions:
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for face in faces:
        lines.append("f " + " ".join(str(i + 1) for i in face))
    return "\n".join(lines) + "\n"

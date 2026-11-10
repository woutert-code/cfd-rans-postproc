"""Generator voor kleine, fictieve OpenFOAM-testcases (binaire schrijfwijze).

Bouwt een gestructureerde hexamesh met dezelfde bestandsindeling als de
echte v2006-cases, zodat alle lezers van src/cfd_postproc/of_io.py
getest kunnen worden zonder gevoelige data. Volledig fictief: geometrie,
velden en waarden hebben geen relatie met echte sporters.
"""

from __future__ import annotations

import os

import numpy as np

BANNER = (
    "/*--------------------------------*- C++ -*----------------------------------*\\\n"
    "| =========                 |                                                 |\n"
    "| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |\n"
    "|  \\\\    /   O peration     |                                               |\n"
    "|   \\\\  /    A nd           | Web:  www.openfoam.org                         |\n"
    "|    \\\\/     M anipulation  |                                                 |\n"
    "\\*---------------------------------------------------------------------------*/\n"
)
DIVIDER = "// " + "* " * 32 + "* //\n"


def _foam_header(obj: str, location: str, extra: str = "") -> bytes:
    head = BANNER + "FoamFile\n{\n    version     2.0;\n    format      binary;\n"
    head += f"    class       {extra};\n" if extra else ""
    head += f'    arch        "LSB;label=32;scalar=64";\n'
    head += '    location    "' + location + '";\n    object      ' + obj + ';\n}\n'
    return head.encode("ascii") + DIVIDER.encode("ascii")


def _binary_scalar_list(values: np.ndarray | list) -> bytes:
    arr = np.asarray(values, dtype="<f8")
    return str(len(arr)).encode() + b"\n(" + arr.tobytes() + b")\n"


def _binary_vector_list(values_flat: np.ndarray, n_entries: int) -> bytes:
    """List<vector>: count = aantal entries, daarna 3*entries doubles."""
    arr = np.asarray(values_flat, dtype="<f8").reshape(-1)
    assert arr.size == 3 * n_entries, f"vectorlijst: {arr.size} <> 3*{n_entries}"
    return str(n_entries).encode() + b"\n(" + arr.tobytes() + b")\n"


def _binary_label_list(values: np.ndarray | list) -> bytes:
    arr = np.asarray(values, dtype="<i4")
    return str(len(arr)).encode() + b"\n(" + arr.tobytes() + b")\n"


class StructuredCase:
    """Gestructureerde mesh (hexcellen) met de echte bestandsindeling."""

    def __init__(self, nx: int, ny: int, nz: int, dx: float, dy: float, dz: float):
        self.nx, self.ny, self.nz = nx, ny, nz
        self.dx, self.dy, self.dz = dx, dy, dz

        # Punten: id = ix + (nx+1)*(iy + (ny+1)*iz)
        pts = []
        self.point_ids = np.zeros((nx + 1, ny + 1, nz + 1), dtype=np.int64)
        n = 0
        for iz in range(nz + 1):
            for iy in range(ny + 1):
                for ix in range(nx + 1):
                    pts.append((ix * dx, iy * dy, iz * dz))
                    self.point_ids[ix, iy, iz] = n
                    n += 1
        self.points = np.array(pts, dtype=np.float64)

        def cell(i, j, k):
            return i + nx * (j + ny * k)

        self.cell = cell
        self.faces: list[list[int]] = []
        self.face_owner: list[int] = []
        self.face_neighbour: list[int] = []

        # Interne x-faces (normaal +x), y-faces (+y), z-faces (+z).
        def add_face(verts, owner, neighbour=None):
            self.faces.append(verts)
            self.face_owner.append(owner)
            self.face_neighbour.append(neighbour if neighbour is not None else -1)

        # Interne x-slabs
        for i in range(1, nx):
            for j in range(ny):
                for k in range(nz):
                    v = [
                        int(self.point_ids[i, j, k]),
                        int(self.point_ids[i, j + 1, k]),
                        int(self.point_ids[i, j + 1, k + 1]),
                        int(self.point_ids[i, j, k + 1]),
                    ]
                    add_face(v, cell(i - 1, j, k), cell(i, j, k))
        # Interne y-slabs (normaal +y)
        for j in range(1, ny):
            for k in range(nz):
                for i in range(nx):
                    v = [
                        int(self.point_ids[i, j, k]),
                        int(self.point_ids[i, j, k + 1]),
                        int(self.point_ids[i + 1, j, k + 1]),
                        int(self.point_ids[i + 1, j, k]),
                    ]
                    add_face(v, cell(i, j - 1, k), cell(i, j, k))
        # Interne z-slabs (normaal +z)
        for k in range(1, nz):
            for i in range(nx):
                for j in range(ny):
                    v = [
                        int(self.point_ids[i, j, k]),
                        int(self.point_ids[i + 1, j, k]),
                        int(self.point_ids[i + 1, j + 1, k]),
                        int(self.point_ids[i, j + 1, k]),
                    ]
                    add_face(v, cell(i, j, k - 1), cell(i, j, k))

        # Boundaryfaces per patch, in vaste volgorde.
        self.patches: list[dict] = []

        def add_patch(name, ptype, faces_specs):
            start = len(self.faces)
            for verts, owner in faces_specs:
                add_face(verts, owner)
            self.patches.append(
                {"name": name, "type": ptype, "nFaces": len(faces_specs), "startFace": start}
            )

        def x_slab_verts(i, j, k, outward_pos: bool):
            # +x-volgorde: (i,j,k),(i,j+1,k),(i,j+1,k+1),(i,j,k+1)
            p = self.point_ids
            if outward_pos:
                return [
                    int(p[i, j, k]), int(p[i, j + 1, k]),
                    int(p[i, j + 1, k + 1]), int(p[i, j, k + 1]),
                ]
            return [
                int(p[i, j, k]), int(p[i, j, k + 1]),
                int(p[i, j + 1, k + 1]), int(p[i, j + 1, k]),
            ]

        def y_slab_verts(i, j, k, outward_pos: bool):
            p = self.point_ids
            if outward_pos:
                return [
                    int(p[i, j, k]), int(p[i, j, k + 1]),
                    int(p[i + 1, j, k + 1]), int(p[i + 1, j, k]),
                ]
            return [
                int(p[i, j, k]), int(p[i + 1, j, k]),
                int(p[i + 1, j, k + 1]), int(p[i, j, k + 1]),
            ]

        def z_slab_verts(i, j, k, outward_pos: bool):
            p = self.point_ids
            if outward_pos:
                return [
                    int(p[i, j, k]), int(p[i + 1, j, k]),
                    int(p[i + 1, j + 1, k]), int(p[i, j + 1, k]),
                ]
            return [
                int(p[i, j, k]), int(p[i, j + 1, k]),
                int(p[i + 1, j + 1, k]), int(p[i + 1, j, k]),
            ]

        # pilot: atleet op de x=max-slab voor j,k in j0..j1, k0..k1
        self.body_jk: list[tuple[int, int]] = []
        pilot_faces = []
        other_xmax = []
        for j in range(ny):
            for k in range(nz):
                owner = cell(nx - 1, j, k)
                v = x_slab_verts(nx, j, k, outward_pos=True)
                if (j, k) in self.body_set():
                    pilot_faces.append((v, owner))
                    self.body_jk.append((j, k))
                else:
                    other_xmax.append((v, owner))
        add_patch("inlet", "patch", [
            (x_slab_verts(0, j, k, outward_pos=False), cell(0, j, k))
            for j in range(ny) for k in range(nz)
        ])
        add_patch("ymin", "patch", [
            (y_slab_verts(i, 0, k, outward_pos=False), cell(i, 0, k))
            for i in range(nx) for k in range(nz)
        ])
        add_patch("ymax", "patch", [
            (y_slab_verts(i, ny, k, outward_pos=True), cell(i, ny - 1, k))
            for i in range(nx) for k in range(nz)
        ])
        add_patch("ground", "wall", [
            (z_slab_verts(i, j, 0, outward_pos=False), cell(i, j, 0))
            for i in range(nx) for j in range(ny)
        ])
        add_patch("top", "patch", [
            (z_slab_verts(i, j, nz, outward_pos=True), cell(i, j, nz - 1))
            for i in range(nx) for j in range(ny)
        ])
        add_patch("pilot", "wall", pilot_faces)
        add_patch("outlet", "patch", other_xmax)

    def body_set(self):
        # Atleetblok: j in 0..ceil(ny/2), k in 0..ceil(nz/2)
        jmax = max(1, self.ny // 2 + 1)
        kmax = max(1, self.nz // 2 + 1)
        return set((j, k) for j in range(jmax) for k in range(kmax))

    # ---------- schrijven ----------

    def write(self, case_dir: str, time: str = "2") -> None:
        pm = os.path.join(case_dir, "constant", "polyMesh")
        td = os.path.join(case_dir, time)
        os.makedirs(pm, exist_ok=True)
        os.makedirs(td, exist_ok=True)
        os.makedirs(os.path.join(case_dir, "system"), exist_ok=True)

        with open(os.path.join(pm, "points"), "wb") as f:
            f.write(_foam_header("points", "constant/polyMesh"))
            f.write(b"\n")
            f.write(_binary_scalar_list(self.points.reshape(-1)))
            f.write(b"\n")

        with open(os.path.join(pm, "faces"), "wb") as f:
            f.write(_foam_header("faces", "constant/polyMesh"))
            f.write(b"\n")
            counts = np.array([len(v) for v in self.faces], dtype="<i4")
            offsets = np.zeros(len(counts) + 1, dtype="<i4")
            offsets[1:] = np.cumsum(counts)
            f.write(str(len(offsets)).encode() + b"\n(")
            f.write(offsets.tobytes())
            flat = np.concatenate([np.array(v, dtype="<i4") for v in self.faces])
            f.write(flat.tobytes())
            f.write(b")\n\n")

        with open(os.path.join(pm, "owner"), "wb") as f:
            f.write(_foam_header("owner", "constant/polyMesh"))
            f.write(b"\n")
            f.write(_binary_label_list(self.face_owner))
            f.write(b"\n")

        with open(os.path.join(pm, "neighbour"), "wb") as f:
            n_int = sum(1 for x in self.face_neighbour if x >= 0)
            f.write(_foam_header("neighbour", "constant/polyMesh"))
            f.write(b"\n")
            f.write(_binary_label_list([x for x in self.face_neighbour if x >= 0]))
            f.write(b"\n")

        lines = [str(len(self.patches)), "("]
        for p in self.patches:
            lines.append(f"    {p['name']}")
            lines.append("    {")
            lines.append(f"        type            {p['type']};")
            if p["type"] == "wall":
                lines.append("        inGroups        1(wall);")
            lines.append(f"        nFaces          {p['nFaces']};")
            lines.append(f"        startFace       {p['startFace']};")
            lines.append("    }")
        lines.append(")")
        with open(os.path.join(pm, "boundary"), "w") as f:
            f.write(_foam_header("boundary", "constant/polyMesh", extra="polyBoundaryMesh").decode("ascii"))
            f.write("\n" + "\n".join(lines) + "\n\n")

        # Velden
        n_cells = self.nx * self.ny * self.nz
        p_internal = np.full(n_cells, 10.0)
        self._write_scalar_field(os.path.join(td, "p"), p_internal)
        self._write_vector_field(os.path.join(td, "U"), n_cells)

        pilot_patch = next(p for p in self.patches if p["name"] == "pilot")
        self.n_pilot_faces = pilot_patch["nFaces"]
        self._write_vector_field(
            os.path.join(td, "wallShearStress"),
            0,
            internal_uniform=(0, 0, 0),
            patch_data={"pilot": self.n_pilot_faces},
        )

        with open(os.path.join(case_dir, "system", "Variables"), "w") as f:
            f.write(BANNER.replace("F ield", "F ield"))
            f.write("FoamFile\n{\n    version     2.0;\n    format      ascii;\n    object      Variables;\n}\n")
            f.write(DIVIDER)
            f.write("\nu_inlet  16.0;\n")

    def _write_scalar_field(self, path: str, internal: np.ndarray) -> None:
        with open(path, "wb") as f:
            f.write(_foam_header("p", "2", extra="volScalarField"))
            f.write(b"\ndimensions      [0 2 -2 0 0 0 0];\n\n")
            if len(internal) == 0:
                f.write(b"internalField   uniform 0;\n\n")
            else:
                f.write(b"internalField   nonuniform List<scalar> \n")
                f.write(_binary_scalar_list(internal))
                f.write(b"\n")
            f.write(b"boundaryField\n{\n")
            for p in self.patches:
                f.write(f"    {p['name']}\n    {{\n        type            zeroGradient;\n    }}\n".encode("ascii"))
            f.write(b"}\n")

    def _write_vector_field(self, path, n_entries, internal_uniform=None, patch_data=None) -> None:
        objname = "wallShearStress" if internal_uniform is not None else "U"
        dims = "[0 2 -2 0 0 0 0];" if internal_uniform is not None else "[0 1 -1 0 0 0 0];"
        with open(path, "wb") as f:
            f.write(_foam_header(objname, "2", extra="volVectorField"))
            f.write(b"\ndimensions      " + dims.encode() + b"\n\n")
            if internal_uniform is not None:
                f.write(
                    f"internalField   uniform ({internal_uniform[0]} {internal_uniform[1]} {internal_uniform[2]});\n\n".encode()
                )
            else:
                internal = np.tile(np.array([16.0, 0.0, 0.0]), (n_entries, 1)).reshape(-1)
                f.write(b"internalField   nonuniform List<vector> \n")
                f.write(_binary_vector_list(internal, n_entries))
                f.write(b"\n")
            f.write(b"boundaryField\n{\n")
            for p in self.patches:
                entries = (patch_data or {}).get(p["name"])
                f.write(f"    {p['name']}\n    {{\n".encode("ascii"))
                if entries is not None:
                    vals = np.tile(np.array([0.5, 0.0, 0.0]), (entries, 1)).reshape(-1)
                    f.write(b"        type            calculated;\n        value           nonuniform List<vector> \n")
                    f.write(_binary_vector_list(vals, entries))
                else:
                    f.write(b"        type            zeroGradient;\n")
                f.write(b"    }\n")
            f.write(b"}\n")

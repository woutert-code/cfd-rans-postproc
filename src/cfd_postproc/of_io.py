"""Lezen van OpenFOAM-cases (ESI v2006-stijl, binaire schrijfwijze).

Deze module leest polyMesh- en veldbestanden direct in numpy, zonder
OpenFOAM-installatie. Alles wordt little-endian gelezen volgens de
arch-regel ``LSB;label=32;scalar=64``. Grote interne velden worden
geëvalueerd als float32 om het geheugengebruik te beperken; binary data
wordt opgezocht op byte-offset zodat patchwaarden uit grote velden
(pValidate zeroGradient-kanten) zonder tussenkomst van ParaView volgen.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import numpy as np

# Einde van de FoamFile-banner: '// * * * * ... * //'
_BODY_START_RE = re.compile(rb"// ?\*(?: ?\*)* ?//\r?\n")


def body_offset(raw: bytes) -> int:
    """Byte-offset direct na de FoamFile-header."""
    m = _BODY_START_RE.search(raw)
    if m is None:
        raise ValueError("FoamFile-banner ('// * * ... * //') niet gevonden")
    return m.end()


def _read_first_chunk(path: str, size: int = 65536) -> bytes:
    with open(path, "rb") as f:
        return f.read(size)


def _parse_uniform_value(token: str, ncomp: int | None):
    txt = token.strip().rstrip(";")
    if txt.startswith("("):
        parts = txt.strip("()").split()
        return np.array([float(p) for p in parts], dtype=np.float32)
    val = float(txt)
    if ncomp == 1:
        return np.float32(val)
    return np.full(ncomp, val, dtype=np.float32)


def read_internal_field(path: str, dtype=np.float32) -> np.ndarray:
    """Lees het internalField van een veldbestand.

    Ondersteunt ``uniform`` (scalar of vector) en ``nonuniform List<...>``
    (scalar of vector) in binaire vorm. Voor nonuniform-velden wordt de
    binaire lijst opgezocht en in één keer gelezen met ``np.fromfile``;
    het resultaat wordt als het schaaltypes toelaat naar ``dtype``
    gegoten (standaard float32) om geheugen te sparen.
    """
    head = _read_first_chunk(path)
    off = body_offset(head)
    seg = head[off:]
    m = re.search(
        rb"internalField\s+(uniform|nonuniform)\s+List<(\w+)>\s*(\w|\()",
        seg,
    )
    if m is None:
        m2 = re.search(rb"internalField\s+uniform\s+([^;\n]+)", seg)
        if m2 is None:
            raise ValueError(f"internalField niet herkend in {path}")
        token = m2.group(1).decode("ascii", "replace")
        if "(" in token:
            vec = np.array(
                [float(x) for x in token.strip("() \r\n\t").split()],
                dtype=dtype,
            )
            return vec
        return np.array([float(token)], dtype=dtype)

    kind, listtype = m.group(1), m.group(2).decode("ascii")
    ncomp = 3 if listtype == "vector" else 1

    cm = re.compile(rb"(\d+)\s*\(").search(seg, m.end() - 1)
    if cm is None:
        raise ValueError(f"aantallen van internalField niet gevonden in {path}")
    count = int(cm.group(1))
    data_offset = off + cm.end()

    item_bytes = 8 * ncomp
    if listtype == "vector":
        values = np.fromfile(path, dtype="<f8", count=count * 3, offset=data_offset)
        arr = values.reshape(-1, 3).astype(dtype, copy=False)
    else:
        arr = np.fromfile(path, dtype="<f8", count=count, offset=data_offset).astype(
            dtype, copy=False
        )
    return arr


def read_patch_values(path: str) -> dict[str, np.ndarray]:
    """Lees de boundaryField-waarden per patch uit een veldbestand.

    Returned een dict met patchnaam -> ndarray (n, 3) voor vectoren of
    (n,) voor scalairen. Uniforme patchwaarden worden herhaald over het
    aantal faces van de patch (via de boundary-file als die al geparseerd
    is, anders als lengte-1rray). Patches zonder data (zoals zeroGradient)
    worden overgeslagen.
    """
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        raw = f.read()
    off = body_offset(raw)
    i = raw.find(b"boundaryField", off)
    if i < 0:
        return {}
    region = raw[i:]
    # neutraliseer binaire interne data vóór boundaryField niet nodig:
    # boundaryField staat ná de interne data; region is nu ascii+binaire mix.
    del raw

    result: dict[str, np.ndarray] = {}
    block_re = re.compile(rb"([\w.\-]+)\s*\{([^{}]*)\}", re.S)
    for m in block_re.finditer(region):
        name = m.group(1).decode("ascii")
        body = m.group(2)
        vm = re.search(rb"nonuniform\s+List<(\w+)>\s*(\d+)\s*\(", body)
        if vm is not None:
            ncomp = 3 if vm.group(1) == b"vector" else 1
            count = int(vm.group(2))
            # vm is gematcht binnen body (m.group(2)), die in region begint
            # op m.start(2): absolute bestandsoffset = i + m.start(2) + vm.end().
            abs_off_in_file = i + m.start(2) + vm.end()
            if ncomp == 3:
                v = np.fromfile(path, dtype="<f8", count=count * 3, offset=abs_off_in_file)
                result[name] = v.reshape(-1, 3).astype(np.float32, copy=False)
            else:
                result[name] = np.fromfile(
                    path, dtype="<f8", count=count, offset=abs_off_in_file
                ).astype(np.float32, copy=False)
            continue
        um = re.search(rb"value\s+uniform\s+([^;\n]+)", body)
        if um is not None:
            tok = um.group(1).decode("ascii", "replace").strip()
            vals = [float(x) for x in tok.strip("() ").split()] or [0.0]
            result[name] = np.array([vals], dtype=np.float32)[0]
    del region, size
    return result


@dataclass
class PatchInfo:
    name: str
    patch_type: str
    n_faces: int
    start_face: int


@dataclass
class FoamMesh:
    """Minimale polyMesh-weergave: punten, face-vertexlijsten, connectiviteit."""

    points: np.ndarray  # (n.points, 3) float32
    face_offsets: np.ndarray  # int32, lengte n_faces + 1, sentinel-eerste
    face_verts: np.ndarray  # int32, platte vertexindices
    owner: np.ndarray  # int32 per face
    neighbour: np.ndarray  # int32 per interne face
    patches: list = field(default_factory=list)

    @property
    def n_faces(self) -> int:
        return len(self.face_offsets) - 1

    def face_vert_counts(self) -> np.ndarray:
        return self.face_offsets[1:] - self.face_offsets[:-1]

    def patch(self, name: str) -> PatchInfo:
        for p in self.patches:
            if p.name == name:
                return p
        raise KeyError(f"patch '{name}' niet gevonden in boundary-file")

    def face_ids_of_patch(self, name: str) -> np.ndarray:
        p = self.patch(name)
        return np.arange(p.start_face, p.start_face + p.n_faces, dtype=np.int64)


def _read_binary_label_list(path: str, item_type: str, ncomp: int = 1) -> np.ndarray:
    """Lees '<count>\\n(<binaire labels of scalars>)' na header."""
    head = _read_first_chunk(path)
    off = body_offset(head)
    seg = head[off:]
    skipped = len(seg) - len(seg.lstrip())
    m = re.compile(rb"(\d+)\s*\(").match(seg.lstrip())
    if m is None:
        raise ValueError(f"binaire lijst niet herkend in {path}")
    count = int(m.group(1))
    data_off = off + skipped + m.end()
    if item_type == "label":
        arr = np.fromfile(path, dtype="<i4", count=count * ncomp, offset=data_off)
    else:
        arr = np.fromfile(path, dtype="<f8", count=count * ncomp, offset=data_off)
    return arr


def read_boundary(path: str) -> list:
    """Parse de ascii boundary-file (patchnamen, type, nFaces, startFace)."""
    with open(path, "r", encoding="ascii", errors="replace") as f:
        raw = f.read()
    m = re.search(r"\(\s*(.*?)\s*\)\s*$", raw, re.S)
    body = m.group(1) if m else raw
    patches = []
    block_re = re.compile(r"([\w.\-]+)\s*\{([^{}]*)\}", re.S)
    for bm in block_re.finditer(body):
        name = bm.group(1)
        d = bm.group(2)
        tm = re.search(r"^\s*type\s+(\w+)\s*;", d, re.M)
        nf = re.search(r"nFaces\s+(\d+)\s*;", d)
        sf = re.search(r"startFace\s+(\d+)\s*;", d)
        if tm and nf and sf:
            patches.append(
                PatchInfo(name, tm.group(1), int(nf.group(1)), int(sf.group(1)))
            )
    return patches


def read_mesh(case_dir: str, points_as_float32: bool = True) -> FoamMesh:
    """Lees constant/polyMesh binair: points, faces, owner, neighbour, boundary."""
    pm = os.path.join(case_dir, "constant", "polyMesh")

    pts = _read_binary_label_list(os.path.join(pm, "points"), "scalar", ncomp=3)
    points = pts.reshape(-1, 3)
    if points_as_float32:
        points = points.astype(np.float32, copy=False)

    # faces: compact lijst '<n_offsets>(' int32, daarna platte vertexlijst.
    fpath = os.path.join(pm, "faces")
    head = _read_first_chunk(fpath)
    off = body_offset(head)
    seg = head[off:]
    skipped = len(seg) - len(seg.lstrip())
    m = re.compile(rb"(\d+)\s*\(").match(seg.lstrip())
    if m is None:
        raise ValueError("faces-file niet herkend")
    n_off = int(m.group(1))
    binary_start = off + skipped + m.end()
    offsets = np.fromfile(fpath, dtype="<i4", count=n_off, offset=binary_start)
    fsize = os.path.getsize(fpath)
    n_verts = (fsize - binary_start - n_off * 4) // 4
    if n_verts < 0:
        n_verts = 0
    face_verts = np.fromfile(
        fpath, dtype="<i4", count=n_verts, offset=binary_start + n_off * 4
    )
    if int(offsets[-1]) != n_verts:
        raise ValueError(
            f"faces-file inconsistent: laatste offset {offsets[-1]} <> {n_verts} vertices"
        )

    owner = _read_binary_label_list(os.path.join(pm, "owner"), "label")
    neighbour = _read_binary_label_list(os.path.join(pm, "neighbour"), "label")

    patches = read_boundary(os.path.join(pm, "boundary"))
    n_faces_mesh = len(offsets) - 1
    if not patches:
        raise ValueError("geen patches gevonden in boundary-file")
    interne_faces = patches[0].start_face
    totale_randfaces = sum(p.n_faces for p in patches)
    if interne_faces + totale_randfaces != n_faces_mesh:
        raise ValueError(
            f"boundary-file ({interne_faces} interne + {totale_randfaces} randfaces) "
            f"klopt niet met faces-file ({n_faces_mesh} faces)"
        )
    if len(owner) != n_faces_mesh:
        raise ValueError("owner-lijst heeft niet het verwachte aantal faces")

    return FoamMesh(points, offsets, face_verts, owner, neighbour, patches)


def latest_time(case_dir: str) -> str:
    """Hoogste numerieke tijdmap in de case (0, constant en logs genegeerd)."""
    times = []
    for entry in os.listdir(case_dir):
        full = os.path.join(case_dir, entry)
        if os.path.isdir(full) and entry.replace(".", "", 1).isdigit():
            times.append((float(entry), entry))
    if not times:
        raise ValueError(f"geen tijdmappen gevonden in {case_dir}")
    return max(times)[1]


def read_variable(case_dir: str, name: str) -> float | None:
    """Lees een variabele uit system/Variables (bijv. u_inlet = 16.0)."""
    path = os.path.join(case_dir, "system", "Variables")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="ascii", errors="replace") as f:
        raw = f.read()
    m = re.search(rf"^\s*{re.escape(name)}\s+([\d.eE+\-]+)\s*;", raw, re.M)
    if m is None:
        return None
    return float(m.group(1))

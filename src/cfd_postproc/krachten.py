"""Geometrie en krachten op atleet-patches: oppervlaktevectoren, druk- en
wrijvingsbijdrage, frontaal oppervlak.

Conventies (simpleFoam, kinematische druk p [m2/s2]):
- p is kinematisch: F_druk = rho * som(p_cel * Sf).  Sf wijst bij
  randfaces naar buiten het stromingsdomein, dus óp het lichaam: de
  drukkracht op de atleet is +rho * p * Sf.
- wallShearStress staat eveneens in kinematische eenheden [m2/s2] per
  wandface. De schuifkracht op de atleet is SHEAR_SIGN * som(wss * |Sf|);
  SHEAR_SIGN is gecontroleerd op gelijke renderrichting (zie tests en
  plan-van-aanpak.md, sectie 12).
"""

from __future__ import annotations

import numpy as np

SHEAR_SIGN = 1.0


def face_geometry(mesh, face_ids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Oppervlaktevector (Sf) en zwaartepunt per face, gevectoriseerd.

    Polygons: Sf = 0.5 * som(v_i x v_{i+1}) over de gesloten vertexlus;
    zwaartepunt = gemiddelde van de hoekpunten (voldoende voor versie 1).
    """
    offs = mesh.face_offsets
    verts = mesh.face_verts
    pts = mesh.points
    face_ids = np.asarray(face_ids)
    counts = offs[face_ids + 1] - offs[face_ids]

    sf = np.zeros((len(face_ids), 3), dtype=np.float64)
    centroids = np.zeros((len(face_ids), 3), dtype=np.float64)

    for k in np.unique(counts):
        sel = np.nonzero(counts == k)[0]
        starts = offs[face_ids[sel]]
        idx = starts[:, None] + np.arange(k)[None, :]
        p = pts[verts[idx]]  # (n, k, 3)
        cross = np.cross(p, np.roll(p, -1, axis=1)).sum(axis=1)
        sf[sel] = 0.5 * cross
        centroids[sel] = p.mean(axis=1)
    return sf, centroids


def pressure_drag(mesh, p_internal: np.ndarray, face_ids: np.ndarray, rho: float) -> np.ndarray:
    """Drukkracht per richting op de gegeven faces (float32-vectoren)."""
    sf, _ = face_geometry(mesh, face_ids)
    owners = mesh.owner[face_ids].astype(np.int64)
    p_wall = p_internal[owners].astype(np.float64)
    return rho * (p_wall[:, None] * sf).sum(axis=0)


def shear_drag(mesh, wss_values: np.ndarray, face_ids: np.ndarray, rho: float) -> np.ndarray:
    """Schuifkracht per richting; wss_values: (n_faces, 3) op de faces."""
    sf, _ = face_geometry(mesh, face_ids)
    area = np.linalg.norm(sf, axis=1)  # |Sf|
    return SHEAR_SIGN * rho * (wss_values.astype(np.float64) * area[:, None]).sum(axis=0)


def frontal_area(mesh, face_ids_per_group: dict[str, np.ndarray], dx: float = 0.002) -> dict[str, float]:
    """Frontaal oppervlak: gesilhouette van alle gegeven faces op het
    yz-vlak (loodrecht op de stroomrichting x), via rasterisatie.

    Geeft per groep (bijv. 'pilot', 'stoker') en als 'totaal' (unie van
    alle groepen) het oppervlak in m2. Resolutie 'dx' in meters.
    """
    from PIL import Image, ImageDraw

    all_ids = np.concatenate(list(face_ids_per_group.values()))
    polys = _face_vertex_coords(mesh, all_ids)  # dict count -> (n, k, 3)
    yall = np.concatenate([g[:, :, 1].ravel() for g in polys.values()])
    zall = np.concatenate([g[:, :, 2].ravel() for g in polys.values()])
    ymin, zmin = yall.min(), zall.min()
    ny = int(np.ceil((yall.max() - ymin) / dx)) + 2
    nz = int(np.ceil((zall.max() - zmin) / dx)) + 2

    def raster(ids: np.ndarray) -> "Image.Image":
        img = Image.new("1", (ny, nz), 0)
        draw = ImageDraw.Draw(img)
        for group in _face_vertex_coords(mesh, np.asarray(ids)).values():
            py = (group[:, :, 1] - ymin) / dx
            pz = (group[:, :, 2] - zmin) / dx
            for i in range(len(py)):
                draw.polygon(list(zip(pz[i].tolist(), py[i].tolist())), fill=1)
        return img

    result: dict[str, float] = {}
    masks: dict[str, "Image.Image"] = {}
    for name, ids in face_ids_per_group.items():
        if len(ids) == 0:
            result[name] = 0.0
            continue
        masks[name] = raster(ids)
        result[name] = _mask_area(masks[name], dx)
    # Unie van alle groepen als totale silhouette.
    tot = Image.new("1", (ny, nz), 0)
    for m in masks.values():
        tot = Image.composite(Image.new("1", (ny, nz), 1), tot, m)
    result["totaal"] = _mask_area(tot, dx)
    return result


def _mask_area(img: "Image.Image", dx: float) -> float:
    arr = np.asarray(img.convert("L"))
    return float((arr > 0).sum()) * dx * dx


def _face_vertex_coords(mesh, face_ids: np.ndarray) -> dict[int, np.ndarray]:
    """Vertexcoordinaten per face, gegroepeerd op vertexaantal;
    per groep een (n_faces, n_verts, 3)-array."""
    offs = mesh.face_offsets
    verts = mesh.face_verts
    pts = mesh.points
    face_ids = np.asarray(face_ids)
    counts = offs[face_ids + 1] - offs[face_ids]
    out: dict[int, np.ndarray] = {}
    for k in np.unique(counts):
        sel = np.nonzero(counts == k)[0]
        starts = offs[face_ids[sel]]
        idx = starts[:, None] + np.arange(int(k))[None, :]
        out[int(k)] = pts[verts[idx]]
    return out

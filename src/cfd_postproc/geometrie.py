"""Geometrie-visualisatie van de atleetpatches (bijv. pilot, stoker).

Maakt solid-weergaven van de body-patch-faces uit de polyMesh:

- 2D-aanzichten (vooraanzicht, zijaanzicht, bovenaanzicht): de projectie van
  **alle** faces wordt met PIL gerasteriseerd tot een gevulde silhouette
  (solid, geen point cloud), plus de afmetingen uit de bounding box.
- 3D-figuur: cel-decimatie van het oppervlak (één face per oppervlakte-cel,
  net zo lang tot het aantal polygonen ≤ limiet), als Poly3DCollection in een
  matplotlib-Figure. In een interactieve FigureCanvasTkAgg is die met de muis
  draaibaar.

De figuren worden als matplotlib-``Figure`` teruggegeben (backend-onafhankelijk).
Bij Run_Tandem_027 (~900k body-faces) rasteriseren de 2D-views in seconden;
de 3D gebruikt ≤ DEFAULT_MAX_POLYS_3D polygonen zodat draaien vlot blijft.
"""

from __future__ import annotations

import numpy as np

# view-naam -> (projectie-assen, as-labels, titel)
VIEWS = {
    "front": ((1, 2), ("y [m]", "z [m]"), "Vooraanzicht (y-z vlak)"),
    "side": ((0, 2), ("x [m]", "z [m]"), "Zijaanzicht (x-z vlak)"),
    "top": ((0, 1), ("x [m]", "y [m]"), "Bovenaanzicht (x-y vlak)"),
}

# limiet voor het aantal polygonen in de 3D-figuur (bij meer wordt de
# interactieve rotatie traag; benchmark: 15k ~0.5 s/redraw, 60k ~2.2 s)
DEFAULT_MAX_POLYS_3D = 20_000
# maximale inflatie-factor van polygonen in de 3D-figuur (solid maken)
DEFAULT_MAX_INFLATE = 6.0
# rasterresolutie van de 2D-aanzichten [m]
DEFAULT_RASTER_DX = 0.002


def body_face_ids(mesh, patch_names) -> np.ndarray:
    """Alle face-ids van de gegeven patches; onbekende patches worden overgeslagen."""
    ids = []
    for name in patch_names:
        try:
            ids.append(mesh.face_ids_of_patch(name))
        except KeyError:
            continue
    if not ids:
        raise ValueError(
            f"geen van de patches {tuple(patch_names)} gevonden in de mesh"
        )
    return np.concatenate(ids)


def face_vertex_groups(mesh, face_ids: np.ndarray) -> dict[int, np.ndarray]:
    """Vertexcoördinaten per face, gegroepeerd op vertexaantal;
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


def bounding_box(mesh, face_ids) -> tuple[np.ndarray, np.ndarray]:
    """Bounding box (min, max) over alle hoekpunten van de gegeven faces."""
    groups = face_vertex_groups(mesh, face_ids)
    allpts = np.concatenate([g.reshape(-1, 3) for g in groups.values()])
    return allpts.min(axis=0), allpts.max(axis=0)


def face_centroids_of(mesh, face_ids: np.ndarray) -> np.ndarray:
    """Zwaartepunten (gemiddelde van de hoekpunten) van de gegeven faces."""
    groups = face_vertex_groups(mesh, face_ids)
    cents = []
    for k, g in groups.items():
        cents.append(g.mean(axis=1))
    return np.concatenate(cents)


def sizes_text(bmin: np.ndarray, bmax: np.ndarray) -> str:
    """Afmetingen van de bounding box als leesbare tekst."""
    d = bmax - bmin
    return (
        f"Lengte (x): {d[0]:.3f} m · Breedte (y): {d[1]:.3f} m · "
        f"Hoogte (z): {d[2]:.3f} m"
    )


def raster_view(mesh, face_ids, view: str, dx: float = DEFAULT_RASTER_DX):
    """Rasteriseer de projectie van alle gegeven faces op het view-vlak.

    Retourneert (mask, extent): mask is een bool-array (nv, nh) met de gevulde
    silhouette, extent = (hmin, hmax, vmin, vmax) in meter voor imshow.
    """
    from PIL import Image, ImageDraw

    a, b = VIEWS[view][0]
    groups = face_vertex_groups(mesh, face_ids)
    hall = np.concatenate([g[:, :, a].ravel() for g in groups.values()])
    vall = np.concatenate([g[:, :, b].ravel() for g in groups.values()])
    hmin, vmin = float(hall.min()), float(vall.min())
    nh = int(np.ceil((hall.max() - hmin) / dx)) + 2
    nv = int(np.ceil((vall.max() - vmin) / dx)) + 2

    img = Image.new("1", (nh, nv), 0)
    draw = ImageDraw.Draw(img)
    for g in groups.values():
        ph = (g[:, :, a] - hmin) / dx
        pv = (g[:, :, b] - vmin) / dx
        for i in range(len(ph)):
            draw.polygon(list(zip(ph[i].tolist(), pv[i].tolist())), fill=1)
    mask = np.asarray(img.convert("L")) > 0
    extent = (hmin, hmin + nh * dx, vmin, vmin + nv * dx)
    return mask, extent


def decimate_surface(mesh, face_ids, max_polys: int, start_h: float = 0.005):
    """Cel-decimatie van het oppervlak: één face per oppervlakte-cel.

    De celgrootte h start bij start_h en wordt verdubbeld tot het aantal
    cellen ≤ max_polys; zo blijven de gekozen faces gelijkmatig over het
    oppervlak verdeeld. Retourneert (geselecteerde face-ids, gebruikte h).
    """
    cents = face_centroids_of(mesh, face_ids)
    h = start_h
    while True:
        cells = np.floor(cents / h).astype(np.int64)
        _, first = np.unique(cells, axis=0, return_index=True)
        if len(first) <= max_polys or h > 1.0:
            return np.sort(np.asarray(face_ids)[first]), h
        h *= 2.0


def face_mean_diameter(mesh, face_ids) -> float:
    """Gemiddelde 'diameter' (2*sqrt(opp/pi)) van de gegeven faces."""
    from .krachten import face_geometry

    sf, _ = face_geometry(mesh, np.asarray(face_ids))
    area = np.linalg.norm(sf, axis=1)
    if area.size == 0 or area.mean() <= 0:
        return 0.0
    return float(2.0 * np.sqrt(area.mean() / np.pi))


def inflation_factor(mesh, face_ids, cell_h: float, max_s: float = DEFAULT_MAX_INFLATE) -> float:
    """Inflatie-factor s voor de gedecimeerde polygonen in de 3D-figuur.

    Bij cel-decimatie zijn de cellen (h) vaak veel groter dan de losse faces;
    zonder inflatie blijven er dan gaten (point-cloud uiterlijk). s = h /
    gemiddelde face-diameter, afgekapt op [1, max_s].
    """
    mean_d = face_mean_diameter(mesh, face_ids)
    if mean_d <= 0:
        return 1.0
    return float(min(max(cell_h / mean_d, 1.0), max_s))


def inflate_polygons(polys: list, s: float) -> list:
    """Blaast elk polygon op rond zijn zwaartepunt met factor s (s ≤ 1 = geen)."""
    if s <= 1.0:
        return polys
    out = []
    for p in polys:
        c = p.mean(axis=0)
        out.append(c + s * (p - c))
    return out


def polygons_of(mesh, face_ids) -> list:
    """Lijst van (n, 3) punt-arrays, één per gegeven face."""
    off, verts, pts = mesh.face_offsets, mesh.face_verts, mesh.points
    return [pts[verts[off[i] : off[i + 1]]] for i in face_ids]


def make_view_figure(view: str, mask: np.ndarray, extent, color: str = "#4c72b0"):
    """Matplotlib-Figure van één 2D-view: de gerasteriseerde (solid) silhouette."""
    import matplotlib
    from matplotlib.figure import Figure

    axes, labels, titel = VIEWS[view]
    fig = Figure(figsize=(7, 5), dpi=100)
    ax = fig.add_subplot(111)
    cmap = matplotlib.colormaps["Blues"].with_extremes(bad=(0, 0, 0, 0))
    ax.imshow(
        np.ma.masked_where(~mask, mask.astype(float)),
        extent=extent,
        origin="lower",
        aspect="equal",
        cmap=cmap,
        vmin=0,
        vmax=1,
    )
    ax.set_xlabel(labels[0])
    ax.set_ylabel(labels[1])
    h, v = extent[1] - extent[0], extent[3] - extent[2]
    ax.set_title(f"{titel} — {h:.3f} × {v:.3f} m")
    fig.tight_layout()
    return fig


def make_3d_figure(polys: list, bmin: np.ndarray, bmax: np.ndarray,
                   title: str = "3D-geometrie — sleep om te draaien",
                   color: str = "#4c72b0"):
    """Matplotlib-Figure met 3D-assen; in een interactieve canvas met de muis draaibaar.

    edgecolor = facecolor, zodat de naden tussen de gedecimeerde faces niet
    als gaten zichtbaar zijn (solid uiterlijk).
    """
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = Figure(figsize=(6.5, 6), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    ax.add_collection3d(
        Poly3DCollection(
            polys, facecolor=color, edgecolor=color, linewidth=0.2, shade=False
        )
    )
    d = bmax - bmin
    # bij een plat vlak (min == max op een as) die as iets uit elkaar trekken,
    # anders is de transformatie singulier
    lo = np.where(d > 1e-9, bmin, bmin - 0.01)
    hi = np.where(d > 1e-9, bmax, bmax + 0.01)
    ax.set_xlim(float(lo[0]), float(hi[0]))
    ax.set_ylim(float(lo[1]), float(hi[1]))
    ax.set_zlim(float(lo[2]), float(hi[2]))
    ax.set_box_aspect((max(float(d[0]), 1e-6), max(float(d[1]), 1e-6), max(float(d[2]), 1e-6)))
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_zlabel("z [m]")
    ax.set_title(title)
    return fig

"""Geometrie-visualisatie van de atleetpatches (bijv. pilot, stoker).

Twee bronnen, in volgorde van voorkeur:

1. **STL-bestanden** (aanbevolen): binaire of ascii-STL's per atleet, gezocht
   in ``constant/triSurface`` van de case zelf, of bij de bijbehorende
   mesh-map (broer/zus-map ``Mesh_<rest van de casenaam>`` naast de case).
   Zonder polyMesh te lezen zijn de aanzichten dan binnen een seconde klaar
   en is de oppervlakte de originele CAD-versie in plaats van de gesnapte
   mesh-vlakken. Zie de find_stl_dir/read_stl/read_body_triangles functies.
2. **polyMesh (fallback)**: body-patch-faces uit de mesh, met cel-decimatie
   en inflatie voor de 3D-weergave.

- 2D-aanzichten (vooraanzicht, zijaanzicht, bovenaanzicht): de projectie van
  **alle** triangles/faces wordt met PIL gerasteriseerd tot een gevulde
  silhouette (solid, geen point cloud), plus de afmetingen uit de bounding
  box.
- 3D-figuur: decimatie (één triangle/face per oppervlakte-cel, net zo lang
  tot het aantal polygonen ≤ limiet), als Poly3DCollection in een
  matplotlib-Figure. In een interactieve FigureCanvasTkAgg is die met de muis
  draaibaar.

De figuren worden als matplotlib-``Figure`` teruggegeben (backend-onafhankelijk).
Bij Run_Tandem_027 (~900k body-faces) rasteriseren de 2D-views in seconden;
de 3D gebruikt ≤ DEFAULT_MAX_POLYS_3D polygonen zodat draaien vlot blijft.
"""

from __future__ import annotations

import os
import re
import struct

import numpy as np

# view-naam -> (projectie-assen, as-labels, titel)
VIEWS = {
    "front": ((1, 2), ("y [m]", "z [m]"), "Vooraanzicht (y-z vlak)"),
    "side": ((0, 2), ("x [m]", "z [m]"), "Zijaanzicht (x-z vlak)"),
    "top": ((0, 1), ("x [m]", "y [m]"), "Bovenaanzicht (x-y vlak)"),
}

# diepte-as per view voor de Cp-weergave (painter's algorithm): (as, teken van
# de camerakant). Bij 'front' kijkt de camera vanaf -x (de voorkant van de
# atleet, de stroom loopt in +x-richting), bij 'side' vanaf +y en bij 'top'
# vanaf +z (van boven). De dichtstbijzijnde face wint in de projectie.
VIEW_DEPTH = {"front": (0, -1.0), "side": (1, 1.0), "top": (2, 1.0)}

# limiet voor het aantal polygonen in de 3D-figuur (bij meer wordt de
# interactieve rotatie traag; benchmark: 15k ~0.5 s/redraw, 60k ~2.2 s)
DEFAULT_MAX_POLYS_3D = 20_000
# maximale inflatie-factor van polygonen in de 3D-figuur (solid maken)
DEFAULT_MAX_INFLATE = 6.0
# rasterresolutie van de 2D-aanzichten [m]
DEFAULT_RASTER_DX = 0.002

# kleur per atleetpatch in de aanzichten; de donkerblauwe kleur is exact de
# "Blues"-waarde die de samengevoegde silhouette eerder had (stoker dus
# onveranderd), de pilot lichtblauw. _PATCH_ORDER bepaalt de schildervolgorde:
# later = bovenop, zodat de voorste atleet zichtbaar blijft waar de
# projecties overlappen.
PATCH_COLORS = {"pilot": "#6baed6", "stoker": "#08306b"}
_PATCH_ORDER = ("stoker", "pilot")


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


def make_view_figure(view: str, mask, extent, color: str = "#4c72b0",
                     figsize=(7, 5), dpi: int = 100, with_title: bool = True):
    """Matplotlib-Figure van één 2D-view: de gerasteriseerde (solid) silhouette.

    mask is of één bool-mask (één silhouette, "Blues"-kleur zoals voorheen)
    of een dict {patchnaam: mask}: dan wordt elke body in de kleur uit
    PATCH_COLORS getekend (onbekende patches in `color`), met later in de
    schildervolgorde bovenop. Met figsize/dpi/with_title geschikt gemaakt
    voor de kleine, ingebedde panels in het startscherm (zonder titel; de
    naam staat op het LabelFrame).
    """
    import matplotlib
    from matplotlib.colors import to_rgb
    from matplotlib.figure import Figure

    axes, labels, titel = VIEWS[view]
    fig = Figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111)
    if isinstance(mask, dict):
        volgorde = [n for n in _PATCH_ORDER if n in mask] + sorted(
            set(mask) - set(_PATCH_ORDER)
        )
        nv, nh = next(iter(mask.values())).shape
        rgb = np.ones((nv, nh, 3), dtype=float)
        alpha = np.zeros((nv, nh), dtype=float)
        for naam in volgorde:
            rgb[mask[naam]] = to_rgb(PATCH_COLORS.get(naam, color))
            alpha[mask[naam]] = 1.0
        ax.imshow(
            np.dstack([rgb, alpha]),
            extent=extent,
            origin="lower",
            aspect="equal",
        )
    else:
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
    if with_title:
        h, v = extent[1] - extent[0], extent[3] - extent[2]
        ax.set_title(f"{titel} — {h:.3f} × {v:.3f} m")
    fig.tight_layout()
    return fig


def make_cp_view_figure(view: str, cp_img, extent, cmap: str = "RdBu_r", vmax=None,
                        vmin=None, figsize=(7, 5), dpi: int = 100, with_title: bool = True):
    """Matplotlib-Figure van één 2D-view met de Cp-distributie op het oppervlak.

    cp_img: float-array (nv, nh) met per pixel de Cp van de zichtbare face
    (NaN buiten het lichaam), bijv. gebouwd met raster_view_index +
    cp_image_from_index. extent = (hmin, hmax, vmin, vmax) in meter.

    Divergente kleurschaal (standaard RdBu_r: rood = hoge druk/stagnatie,
    blauw = lage druk/loslating), inclusief colorbar. Zonder vmin/vmax:
    automatisch symmetrisch rond 0, [-max|Cp|, max|Cp|]. Met vmin en/of vmax
    opgegeven wordt dat bereik gebruikt (bijv. vmin=-2, vmax=1; de
    ontbrekende kant wordt dan gespiegeld).
    """
    from matplotlib.figure import Figure

    _axes, labels, titel = VIEWS[view]
    cp = np.ma.masked_invalid(np.asarray(cp_img, dtype=np.float32))
    if vmin is None and vmax is None:
        finite = cp.compressed()
        m = float(np.abs(finite).max()) if finite.size else 1.0
        if not np.isfinite(m) or m <= 0:
            m = 1.0
        vmin, vmax = -m, m
    else:
        if vmax is None:
            vmax = -vmin
        if vmin is None:
            vmin = -vmax
    fig = Figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111)
    im = ax.imshow(
        cp,
        extent=extent,
        origin="lower",
        aspect="equal",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
    )
    fig.colorbar(im, ax=ax, label="Cp [-]")
    ax.set_xlabel(labels[0])
    ax.set_ylabel(labels[1])
    if with_title:
        h, v = extent[1] - extent[0], extent[3] - extent[2]
        ax.set_title(f"{titel} — Cp, {h:.3f} × {v:.3f} m")
    fig.tight_layout()
    return fig


def make_3d_figure(polys: list, bmin: np.ndarray, bmax: np.ndarray,
                   title: str = "3D-geometrie — sleep om te draaien",
                   color: str = "#4c72b0", kleuren: list | None = None):
    """Matplotlib-Figure met 3D-assen; in een interactieve canvas met de muis draaibaar.

    edgecolor = facecolor, zodat de naden tussen de gedecimeerde faces niet
    als gaten zichtbaar zijn (solid uiterlijk).
    """
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = Figure(figsize=(6.5, 6), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    if kleuren is not None:
        # één kleur per polygoon (in het geval van de STL-route: per atleet)
        ax.add_collection3d(
            Poly3DCollection(
                polys, facecolors=kleuren, edgecolors=kleuren,
                linewidth=0.2, shade=False,
            )
        )
    else:
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


# --------------------------------------------------------------------------
# STL-bron (aanbevolen: snel — geen polyMesh nodig — en de originele CAD-,
# in plaats van de gesnapte mesh-oppervlakte)
# --------------------------------------------------------------------------

# ascii-STL: alle 'vertex x y z'-regels
_STL_VERTEX_RE = re.compile(
    rb"vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)"
)


def find_stl_dir(case_dir: str) -> str | None:
    """Zoek de triSurface-map met de STL's van de atleten.

    Volgorde (case bijv. 'Run_Tandem_001', rest = 'Tandem_001'):
    1. ``constant/triSurface`` ín de case-map;
    2. de broer/zus-map ``Mesh_<rest>`` naast de case (OneDrive-structuur:
       ``.../Run_Tandem_027`` en ``.../Mesh_Tandem_027`` in dezelfde map);
    3. ``<bovenliggende map>/Mesh/Mesh_<rest>/constant/triSurface``
       (structuur met aparte Case- en Mesh-mappen, bijv.
       ``E:\\KNWU CFD\\Tandem\\Case\\Run_Tandem_001`` en
       ``E:\\KNWU CFD\\Tandem\\Mesh\\Mesh_Tandem_001``).

    Retourneert het triSurface-map-pad, of None als er nergens STL's staan.
    """
    case_dir = os.path.abspath(case_dir)
    naam = os.path.basename(case_dir.rstrip("\\/"))
    cands = [os.path.join(case_dir, "constant", "triSurface")]
    if naam.startswith("Run_"):
        rest = naam[4:]
        parent = os.path.dirname(case_dir)
        grandparent = os.path.dirname(parent)
        cands.append(os.path.join(parent, "Mesh_" + rest, "constant", "triSurface"))
        if grandparent:
            cands.append(
                os.path.join(grandparent, "Mesh", "Mesh_" + rest, "constant", "triSurface")
            )
    elif naam.startswith("Mesh_"):
        # ook ondersteunen dat de gebruiker een mesh-map als 'case' kiest
        cands.append(
            os.path.join(os.path.dirname(case_dir), "Run_" + naam[5:], "constant", "triSurface")
        )
    for cand in cands:
        if os.path.isdir(cand) and any(
            f.lower().endswith(".stl") for f in _listdir_safe(cand)
        ):
            return cand
    return None


def _listdir_safe(path: str) -> list:
    try:
        return os.listdir(path)
    except OSError:
        return []


def read_stl(path: str) -> np.ndarray:
    """Lees één STL-bestand als (n, 3, 3) float32 driehoekcoördinaten.

    Herkent binair (structuur: 80-byte header + uint32 aantal + n keer
    50 bytes) en ascii ('vertex x y z'-regels).
    """
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) >= 84:
        (n,) = struct.unpack_from("<I", raw, 80)
        if len(raw) == 84 + 50 * n:
            rows = np.frombuffer(raw, dtype=np.uint8, count=50 * n, offset=84)
            rows = rows.reshape(n, 50) if n else np.empty((0, 50), np.uint8)
            # per driehoek: 12 bytes normaal, 12..48 de 3 hoekpunten, 2 bytes attr
            verts = rows[:, 12:48].copy().view("<f4").reshape(n, 3, 3)
            return verts.astype(np.float32)
    vals = np.array([[float(x) for x in tup] for tup in _STL_VERTEX_RE.findall(raw)])
    if vals.size == 0 or vals.size % 9 != 0:
        raise ValueError(f"STL niet herkend (binair of ascii): {path}")
    return vals.reshape(-1, 3, 3).astype(np.float32)


def read_body_triangles(case_dir: str, patch_names) -> dict[str, np.ndarray] | None:
    """Driehoeken per atleetpatch uit de STL's van de case.

    Zoekt per patch ``<patchnaam>.stl`` (hoofdletterongevoelig) in de
    triSurface-map van find_stl_dir. Retourneert None als er geen STL's zijn
    of niet élk patch gevonden wordt, zodat de aanroeper naar de polyMesh
    terugvalt.
    """
    stl_dir = find_stl_dir(case_dir)
    if stl_dir is None:
        return None
    files = {
        os.path.splitext(f)[0].lower(): os.path.join(stl_dir, f)
        for f in _listdir_safe(stl_dir)
        if f.lower().endswith(".stl")
    }
    tris: dict[str, np.ndarray] = {}
    for name in patch_names:
        path = files.get(name.lower())
        if path is None:
            return None
        tris[name] = read_stl(path)
    return tris


def bounding_box_triangles(tris: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bounding box (min, max) over alle hoekpunten van de driehoeken."""
    allpts = np.asarray(tris, dtype=np.float32).reshape(-1, 3)
    return allpts.min(axis=0), allpts.max(axis=0)


def raster_view_triangles(
    tris: np.ndarray, view: str, dx: float = DEFAULT_RASTER_DX, extent=None
):
    """Zelfde interface als raster_view, maar voor STL-driehoeken.

    Retourneert (mask, extent): gevulde silhouette op het view-vlak en de
    omringende rechthoek in meters voor imshow. Rasterisatie is gevectoriseerd
    in numpy: elke driehoek vult zijn pixel-bbox (STL-driehoeken zijn
    typisch kleiner dan 1 pixel; een binnen-test op pixelcentra zou dunne
    driehoeken laten wegvallen). De silhouette kan daardoor ~1 pixel (~dx)
    breder lijken; voor een visuele check onmerkbaar.

    Met extent=(h0, h1, v0, v1) vallen driehoeken van meerdere bodies op
    hetzelfde rooster (zelfde oorsprong en afmeting), zodat de masks per body
    met verschillende kleuren over elkaar kunnen worden getekend.
    """
    a, b = VIEWS[view][0]
    tris = np.asarray(tris, dtype=np.float32).reshape(-1, 3, 3)
    hall = tris[:, :, a].ravel()
    vall = tris[:, :, b].ravel()
    if extent is None:
        hmin, vmin = float(hall.min()), float(vall.min())
        nh = int(np.ceil((hall.max() - hmin) / dx)) + 2
        nv = int(np.ceil((vall.max() - vmin) / dx)) + 2
    else:
        hmin, hmax, vmin, vmax = (float(e) for e in extent)
        nh = int(np.ceil((hmax - hmin) / dx)) + 1
        nv = int(np.ceil((vmax - vmin) / dx)) + 1

    ph = (tris[:, :, a] - hmin) / dx  # (n, 3) pixel-coordinaten
    pv = (tris[:, :, b] - vmin) / dx
    mask = _rasterize_triangles_2d(ph, pv, nh, nv)
    if extent is None:
        extent = (hmin, hmin + nh * dx, vmin, vmin + nv * dx)
    return mask, tuple(float(e) for e in extent)


def _bbox_arrays(ph: np.ndarray, pv: np.ndarray, nh: int, nv: int):
    """Pixel-bbox (h0, h1, v0, v1) per polygon uit (n, k) pixelcoördinaten."""
    h0 = np.clip(np.floor(ph.min(axis=1)).astype(np.int64), 0, nh - 1)
    h1 = np.clip(np.ceil(ph.max(axis=1)).astype(np.int64), 0, nh - 1)
    v0 = np.clip(np.floor(pv.min(axis=1)).astype(np.int64), 0, nv - 1)
    v1 = np.clip(np.ceil(pv.max(axis=1)).astype(np.int64), 0, nv - 1)
    return h0, h1, v0, v1


def _rasterize_bboxes(h0, h1, v0, v1, nh: int, nv: int, out: np.ndarray, labels=None):
    """Vul `out` met de pixel-bbox van elke rij, in de gegeven volgorde.

    out is een bool-mask (dan wordt True gezet) of een int32-beeld (dan wordt
    `labels[rij]` geschreven, of het rijnummer als labels=None). Werkt in
    blokken van ~1M kandidaat-pixels zodat het geheugengebruik begrensd blijft.
    Latere rijen overschrijven eerdere: bij een int-beeld met rijen gesorteerd
    van ver naar dichtbij geeft dat painter's algorithm (dichtstbij wint).
    """
    n = len(h0)
    if n == 0:
        return out
    bw = h1 - h0 + 1  # bbox-breedte in pixels per rij
    bh = v1 - v0 + 1
    per_tri = bw * bh  # pixels per rij

    tot = int(per_tri.sum())
    if tot == 0:
        return out
    cum = np.cumsum(per_tri)

    is_bool = out.dtype == np.bool_
    BLOCK = 1_000_000
    g0 = 0  # globale pixel-offset van het blok
    i0 = 0  # eerste rij van het blok
    while g0 < tot:
        i1 = int(np.searchsorted(cum, g0 + BLOCK, side="right"))
        i1 = max(i1, i0 + 1, min(i1, n))  # minimaal één rij per blok
        counts = per_tri[i0:i1]
        tot_blk = int(counts.sum())
        row = np.repeat(
            np.arange(i1 - i0, dtype=np.int64) + i0, counts
        )
        starts = cum[i0:i1] - counts  # globale start-index per rij
        within = np.arange(tot_blk, dtype=np.int64) + g0 - starts[row - i0]
        bw_t = bw[row]
        bx = within % bw_t
        by = within // bw_t
        px = h0[row] + bx
        py = v0[row] + by
        if is_bool:
            out[py, px] = True
        else:
            out[py, px] = labels[row] if labels is not None else row
        g0 = int(cum[i1 - 1])
        i0 = i1
    return out


def _rasterize_triangles_2d(ph: np.ndarray, pv: np.ndarray, nh: int, nv: int) -> np.ndarray:
    """Vul een (nv, nh)-masker met de pixel-bbox van elke driehoek.

    ph, pv: (n, 3) driehoekcoordinaten in pixelruimte. Werkt in blokken van
    ~1M kandidaat-pixels zodat het geheugengebruik begrensd blijft.
    """
    mask = np.zeros((nv, nh), dtype=bool)
    if ph.shape[0] == 0:
        return mask
    h0, h1, v0, v1 = _bbox_arrays(ph, pv, nh, nv)
    return _rasterize_bboxes(h0, h1, v0, v1, nh, nv, mask)


def raster_view_index(mesh, face_ids, view: str, dx: float = DEFAULT_RASTER_DX, extent=None):
    """Rasteriseer de projectie van alle gegeven faces naar een face-index-beeld.

    Zelfde raster als raster_view, maar per pixel wordt bijgehouden welke face
    daar zichtbaar is: de faces worden op de diepte-as van de view gesorteerd
    (painter's algorithm, van ver naar dichtbij), zodat in de projectie de
    dichtstbijzijnde face wint (bij de Cp-weergave: de kant van de atleet die
    de camera ziet).

    Retourneert (idx, extent): idx is een int32-array (nv, nh) met per pixel
    het rijnummer in `face_ids` van de zichtbare face (-1 = achtergrond);
    extent = (hmin, hmax, vmin, vmax) in meter voor imshow.
    """
    a, b = VIEWS[view][0]
    c, sign = VIEW_DEPTH[view]
    face_ids = np.asarray(face_ids)
    counts = mesh.face_offsets[face_ids + 1] - mesh.face_offsets[face_ids]
    groups = face_vertex_groups(mesh, face_ids)

    hall = np.concatenate([g[:, :, a].ravel() for g in groups.values()])
    vall = np.concatenate([g[:, :, b].ravel() for g in groups.values()])
    if extent is None:
        hmin, vmin = float(hall.min()), float(vall.min())
        nh = int(np.ceil((hall.max() - hmin) / dx)) + 2
        nv = int(np.ceil((vall.max() - vmin) / dx)) + 2
    else:
        hmin, hmax, vmin, vmax = (float(e) for e in extent)
        nh = int(np.ceil((hmax - hmin) / dx)) + 1
        nv = int(np.ceil((vmax - vmin) / dx)) + 1

    # per vertexaantal-groep de pixel-bbox berekenen; de groepen hebben
    # verschillende breedte k, dus NIET de (n, k)-arrays concateneren,
    # maar per groep reduceren naar 1D en dáár concateneren
    h0_l, h1_l, v0_l, v1_l, depth_l, labels_l = [], [], [], [], [], []
    for k in np.unique(counts):
        g = groups[int(k)]
        ph = (g[:, :, a] - hmin) / dx
        pv = (g[:, :, b] - vmin) / dx
        g0, g1, g2, g3 = _bbox_arrays(ph, pv, nh, nv)
        h0_l.append(g0)
        h1_l.append(g1)
        v0_l.append(g2)
        v1_l.append(g3)
        depth_l.append(sign * g[:, :, c].mean(axis=1))
        # originele rijnummers in face_ids (face_vertex_groups groepeert op
        # vertexaantal, dus de concatenatie-volgorde is gegroepeerd)
        labels_l.append(np.nonzero(counts == k)[0].astype(np.int64))
    h0 = np.concatenate(h0_l)
    h1 = np.concatenate(h1_l)
    v0 = np.concatenate(v0_l)
    v1 = np.concatenate(v1_l)
    depth = np.concatenate(depth_l)
    labels = np.concatenate(labels_l)

    # painter's algorithm: van ver naar dichtbij tekenen (oplopende diepte),
    # de dichtstbijzijnde face wordt dus het laatst geschreven en wint
    order = np.argsort(depth, kind="stable")
    h0, h1, v0, v1 = h0[order], h1[order], v0[order], v1[order]
    lab = labels[order]
    idx = np.full((nv, nh), -1, dtype=np.int32)
    _rasterize_bboxes(h0, h1, v0, v1, nh, nv, idx, labels=lab)
    if extent is None:
        extent = (hmin, hmin + nh * dx, vmin, vmin + nv * dx)
    return idx, tuple(float(e) for e in extent)


def cp_image_from_index(idx: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Zet een face-index-beeld om in een float32 veld-beeld (NaN = achtergrond).

    values: per face (in de volgorde van face_ids waarom idx is gebouwd).
    """
    values = np.asarray(values, dtype=np.float32)
    img = np.full(idx.shape, np.nan, dtype=np.float32)
    m = idx >= 0
    img[m] = values[idx[m]]
    return img


def decimate_triangles(
    tris: np.ndarray, max_polys: int, start_h: float = 0.005
) -> tuple[np.ndarray, float, float]:
    """Decimatie van STL-driehoeken: één triangle per oppervlakte-cel.

    Retourneert (geselecteerde driehoeken, gebruikte celgrootte h,
    inflatie-factor s). De inflatie komt overeen met die van de polyMesh-
    route: s = h / gemiddelde triangle-diameter, afgekapt op [1, max_s].

    De celgrootte wordt direct geschat vanuit het totale oppervlak
    (h ≈ sqrt(A / max_polys)), zodat meestal één np.unique-slag genoeg is
    i.p.v. herhaaldelijk verdubbelen — merkbaar sneller bij ~1M driehoeken.
    """
    tris = np.asarray(tris, dtype=np.float32).reshape(-1, 3, 3)
    cents = tris.mean(axis=1)
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    uit_opp = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    tot_opp = float(uit_opp.sum())
    h = max(float(np.sqrt(tot_opp / max_polys)), start_h) if tot_opp > 0 else start_h
    n_uniq, first = _first_per_cell(cents, h)
    while n_uniq > max_polys and h <= 1.0:
        h *= 2.0
        n_uniq, first = _first_per_cell(cents, h)
    # eventueel verfijnen als de schatting te grof uitviel
    while (
        n_uniq <= max_polys // 8
        and h / 2.0 >= start_h
        and h > start_h
    ):
        h2 = h / 2.0
        n2, f2 = _first_per_cell(cents, h2)
        if n2 > max_polys:
            break
        h, n_uniq, first = h2, n2, f2
    sel = np.sort(first)
    selected = tris[sel]
    s = _inflation_factor_triangles(selected, h)
    return selected, h, s


def _first_per_cell(cents: np.ndarray, h: float) -> tuple[int, np.ndarray]:
    """Aantal bezette oppervlakte-cellen en de index van de eerste triangle
    per cel; snelle variant via een 1D ravel_key i.p.v. np.unique(axis=0)."""
    c = np.floor(cents / h).astype(np.int64)
    c -= c.min(axis=0)
    dims = c.max(axis=0) + 1
    if int(dims[0]) * int(dims[1]) * int(dims[2]) > 2**40:
        # fall-back voor extreem uiteenliggende coordinaten
        _, first = np.unique(c, axis=0, return_index=True)
        return len(first), first
    key = np.ravel_multi_index((c[:, 0], c[:, 1], c[:, 2]), tuple(int(d) for d in dims))
    _, first = np.unique(key, return_index=True)
    return len(first), first


def _inflation_factor_triangles(
    tris: np.ndarray, cell_h: float, max_s: float = DEFAULT_MAX_INFLATE
) -> float:
    """Zelfde regel als inflation_factor, maar voor STL-driehoeken."""
    # oppervlak per driehoek via de kruisproduct-formule
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    uit_opp = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    mean_area = float(uit_opp.mean()) if uit_opp.size else 0.0
    if mean_area <= 0:
        return 1.0
    mean_d = 2.0 * np.sqrt(mean_area / np.pi)
    return float(min(max(cell_h / mean_d, 1.0), max_s))

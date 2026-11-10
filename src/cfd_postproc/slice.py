"""Slice-figuur van de luchtsnelheid (magnitude).

Gebruikt tripcolor voor een nauwkeurige weergave van de echte mesh-geometrie,
i.p.v. histogram2d die de geometrie vervormt.
"""

from __future__ import annotations

import numpy as np

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def face_centroids(points, offsets, labels, block_faces=2_000_000):
    """Zwaartepunt per vlak, in blokken om het geheugengebruik te begrenzen.
    
    Args:
        points: (n_points, 3) float array met coördinaten
        offsets: (n_faces + 1,) int array met start indices
        labels: (n_verts,) int array met vertex indices
        block_faces: maximum aantal faces per blok
        
    Returns:
        (n_faces, 3) float32 array met zwaartepunten
    """
    n_faces = len(offsets) - 1
    cents = np.empty((n_faces, 3), dtype=np.float32)
    f0 = 0
    while f0 < n_faces:
        f1 = min(n_faces, f0 + block_faces)
        v0, v1 = int(offsets[f0]), int(offsets[f1])
        pts = points[labels[v0:v1]].astype(np.float32)
        starts = (offsets[f0:f1] - v0).astype(np.int64)
        sizes = np.diff(offsets[f0 : f1 + 1])
        cents[f0:f1] = np.add.reduceat(pts, starts) / sizes[:, None].astype(np.float32)
        f0 = f1
    return cents


def cell_centers(mesh, log=None):
    """Berekent celzwaartepunten als gemiddelde van de zwaartepunten van de celvlakken.
    
    Args:
        mesh: FoamMesh object met points, face_offsets, face_verts, owner, neighbour, patches
        log: optionele logging functie
        
    Returns:
        (n_cells, 3) float32 array met celzwaartepunten
    """
    # Bereken eerst face centroids
    if log is not None:
        log("face centroids berekenen...")
    face_cents = face_centroids(mesh.points, mesh.face_offsets, mesh.face_verts)
    
    # Celzwaartepunten = gemiddelde van face centroids van owner en neighbour
    # n_cells = max(owner) + 1 (standaard OpenFOAM convention)
    n_cells = int(mesh.owner.max()) + 1
    n_int = len(mesh.neighbour)  # interne faces
    
    owner = mesh.owner.astype(np.int64)
    neighbour = mesh.neighbour.astype(np.int64)
    
    if log is not None:
        log("celzwaartepunten berekenen via bincount...")
    
    # Tel hoeveel faces per cel
    count = np.bincount(owner, minlength=n_cells) + np.bincount(neighbour, minlength=n_cells)
    count[count == 0] = 1  # Voorkom deling door nul
    
    # Accumuleer x, y, z afzonderlijk
    centers = np.empty((n_cells, 3), dtype=np.float32)
    for k in range(3):
        centers[:, k] = (
            np.bincount(owner, weights=face_cents[:, k], minlength=n_cells)
            + np.bincount(neighbour, weights=face_cents[:n_int, k], minlength=n_cells)
        ) / count.astype(np.float32)
    
    return centers


def _plane_coords(arr, axis):
    """Haal coördinaten voor het slice-vlak."""
    if axis == "y":
        return arr[:, 0], arr[:, 2]  # x, z
    if axis == "z":
        return arr[:, 0], arr[:, 1]  # x, y
    return arr[:, 1], arr[:, 2]  # y, z (voor x-slice)


def _plane_labels(axis):
    """Label voor de assen."""
    if axis == "y":
        return "x [m]", "z [m]"
    if axis == "z":
        return "x [m]", "y [m]"
    return "y [m]", "z [m]"


def make_slice_figure(
    cell_centers_arr,
    u_mag,
    mesh_points,
    mesh_faces_offsets,
    mesh_faces_labels,
    body_patch_names,
    mesh_patches,
    axis,
    pos,
    tol,
    u_ref,
    out_png,
    case_name,
    log=None,
):
    """Maak een slice-afbeelding met tripcolor voor nauwkeurige mesh-weergave.
    
    Args:
        cell_centers_arr: (n_cells, 3) array met celzwaartepunten
        u_mag: (n_cells,) array met snelheidsgrootte
        mesh_points: (n_points, 3) array met punten (niet gebruikt in deze versie)
        mesh_faces_offsets: (n_faces + 1,) array met face offsets (niet gebruikt)
        mesh_faces_labels: (n_verts,) array met vertex indices (niet gebruikt)
        body_patch_names: tuple met patch namen voor de geometrie
        mesh_patches: list met PatchInfo objecten
        axis: "x", "y", of "z" voor slice-vlak
        pos: positie van het slice-vlak
        tol: tolerantie voor selectie
        u_ref: referentiesnelheid voor kleurenschaal
        out_png: uitvoerbestandsnaam
        case_name: casenaam voor titel
        log: optionele logging functie
        
    Returns:
        out_png path
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    ai = AXIS_INDEX[axis]
    
    # Selecteer cellen in de slice
    mask = np.abs(cell_centers_arr[:, ai] - pos) <= tol
    if not mask.any():
        raise ValueError(f"geen cellen in het slice-vlak {axis}={pos} (tolerantie {tol})")
    
    if log is not None:
        log("slice: %d cellen geselecteerd, u bereik [%.3f, %.3f]", 
            mask.sum(), float(u_mag[mask].min()), float(u_mag[mask].max()))
    
    # Bereid coördinaten voor
    h, v = _plane_coords(cell_centers_arr[mask], axis)
    xlabel, ylabel = _plane_labels(axis)
    
    # Maak figuur
    fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
    
    # Gebruik tripcolor voor echte mesh-weergave
    if mask.sum() >= 3:
        tpc = ax.tripcolor(
            h, v, 
            u_mag[mask], 
            cmap="viridis",
            vmin=0,
            vmax=u_ref * 1.05,
            shading='gouraud'
        )
        fig.colorbar(tpc, ax=ax, label="|U| [m/s]")
    else:
        sc = ax.scatter(
            h, v, 
            c=u_mag[mask], 
            cmap="viridis", 
            vmin=0, 
            vmax=u_ref * 1.05, 
            s=40
        )
        fig.colorbar(sc, ax=ax, label="|U| [m/s]")
    
    # Voeg geometrie toe (body patches) als zwarte stippen
    if body_patch_names and mesh_patches:
        body_face_inds = []
        for patch_name in body_patch_names:
            try:
                patch = next(p for p in mesh_patches if p.name == patch_name)
                body_face_inds.extend(range(patch.start_face, patch.start_face + patch.n_faces))
            except StopIteration:
                pass
        
        if body_face_inds:
            body_face_inds = np.array(body_face_inds, dtype=int)
            body_face_cents = face_centroids(mesh_points, mesh_faces_offsets, mesh_faces_labels)
            body_h, body_v = _plane_coords(body_face_cents[body_face_inds], axis)
            body_mask = np.abs(body_face_cents[body_face_inds, ai] - pos) <= 2 * tol
            if body_mask.any():
                ax.plot(
                    body_h[body_mask], 
                    body_v[body_mask], 
                    "k.", 
                    ms=1, 
                    alpha=0.5
                )
    
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"{case_name}: luchtsnelheid magnitude, slice {axis} = {pos:.1f} m")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    
    return out_png


# == Legacy functies voor backward compatibility ==

def slice_grid(
    centroids: np.ndarray,
    u_x: np.ndarray,
    y0: float,
    thickness: float,
    n_bins: int = 1000,
    log=None,
):
    """Legacy functie - houdt oude interface."""
    sel = np.abs(centroids[:, 1] - y0) <= thickness / 2.0
    c = centroids[sel]
    ux = u_x[sel]
    if len(c) == 0:
        raise ValueError(
            f"geen cellen binnen de slice-strook |y - {y0}| <= {thickness / 2}"
        )
    if log is not None:
        log("slice: %d cellen geselecteerd, ux bereik [%.3f, %.3f]", len(ux), float(ux.min()), float(ux.max()))
    x_edges = np.linspace(c[:, 0].min(), c[:, 0].max(), n_bins + 1)
    z_edges = np.linspace(c[:, 2].min(), c[:, 2].max(), n_bins + 1)
    counts, _, _ = np.histogram2d(c[:, 0], c[:, 2], bins=(x_edges, z_edges))
    sums, _, _ = np.histogram2d(
        c[:, 0], c[:, 2], bins=(x_edges, z_edges), weights=ux
    )
    with np.errstate(invalid="ignore"):
        grid = sums / counts
    grid = np.nan_to_num(grid, nan=0.0, copy=False)
    return x_edges, z_edges, grid.T, counts.T > 0


def plot_slice(
    x_edges,
    z_edges,
    grid,
    mask,
    png_path: str,
    case_name: str,
    y0: float,
    u_ref: float,
):
    """Legacy functie - houdt oude interface."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    grid_min = float(np.nanmin(grid)) if np.any(np.isfinite(grid)) else 0.0
    grid_max = float(np.nanmax(grid)) if np.any(np.isfinite(grid)) else float(u_ref) * 1.2
    vmin = grid_min * 1.05 if grid_min < 0 else grid_min * 0.95
    vmax = max(grid_max * 1.05, float(u_ref) * 1.2)
    
    im = ax.imshow(
        grid,
        origin="lower",
        extent=(
            x_edges[0],
            x_edges[-1],
            z_edges[0],
            z_edges[-1],
        ),
        aspect="auto",
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
    )
    ax.set_xlabel("x [m]")
    ax.set_ylabel("z [m]")
    ax.set_title(f"{case_name}: luchtsnelheid in x-richting, slice y = {y0:g} m")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("ux [m/s]")
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)

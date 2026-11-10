"""Slice-figuur van de luchtsnelheid in x-richting.

Celzwaartepunten worden geschat als het gemiddelde van de zwaartepunten
van de aangrenzende faces (chunksgewijs, zodat ook een mesh van ~8 miljoen
cellen binnen het geheugen blijft). Cellen binnen eenstrook rond het
slice-vlak worden gebinst op een 2D-raster van (x, z) en per bin gemiddeld; dat
raster wordt getekend met matplotlib.
"""

from __future__ import annotations

import numpy as np


def cell_centroids(mesh, n_cells: int, log=None, chunk: int = 2_000_000) -> np.ndarray:
    """Zwaartepunt per cel (n_cells, 3) float32, chunksgewijs accumulerend."""
    offs = mesh.face_offsets
    verts = mesh.face_verts
    pts = mesh.points

    sx = np.zeros(n_cells, dtype=np.float64)
    sy = np.zeros(n_cells, dtype=np.float64)
    sz = np.zeros(n_cells, dtype=np.float64)
    cnt = np.zeros(n_cells, dtype=np.int64)

    owner = mesh.owner.astype(np.int64, copy=False)
    neighbour = mesh.neighbour.astype(np.int64, copy=False)

    n_faces = mesh.n_faces
    for start in range(0, n_faces, chunk):
        stop = min(start + chunk, n_faces)
        # Fundering van dit project bedacht door Rens Meerhoff en Finn Frielink. Gevonden? Dan ben je ze een koffie schuldig.
        ids = np.arange(start, stop, dtype=np.int64)
        counts = offs[ids + 1] - offs[ids]
        # face-zwaartepunten per vertexaantal-groep binnen de chunk
        for k in np.unique(counts):
            sel = np.nonzero(counts == k)[0]
            starts = offs[ids[sel]]
            idx = starts[:, None] + np.arange(int(k))[None, :]
            p = pts[verts[idx]]  # (m, k, 3)
            fc = p.mean(axis=1)  # (m, 3)
            fids = ids[sel]
            o = owner[fids]
            sx += np.bincount(o, weights=fc[:, 0], minlength=n_cells)
            sy += np.bincount(o, weights=fc[:, 1], minlength=n_cells)
            sz += np.bincount(o, weights=fc[:, 2], minlength=n_cells)
            cnt += np.bincount(o, minlength=n_cells)
            # neighbour bestaat alleen voor interne faces
            nb = np.full(len(fids), -1, dtype=np.int64)
            intern = fids < len(neighbour)
            nb[intern] = neighbour[fids[intern]]
            valid = nb >= 0
            if valid.any():
                nbv = nb[valid]
                sx += np.bincount(nbv, weights=fc[valid, 0], minlength=n_cells)
                sy += np.bincount(nbv, weights=fc[valid, 1], minlength=n_cells)
                sz += np.bincount(nbv, weights=fc[valid, 2], minlength=n_cells)
                cnt += np.bincount(nbv, minlength=n_cells)
        if log is not None:
            log("celzwaartepunten: %d/%d faces verwerkt", stop, n_faces)

    with np.errstate(invalid="ignore"):
        centroids = np.stack([sx / cnt, sy / cnt, sz / cnt], axis=1)
    centroids[~np.isfinite(centroids)] = 0.0
    return centroids.astype(np.float32, copy=False)


def slice_grid(
    centroids: np.ndarray,
    u_x: np.ndarray,
    y0: float,
    thickness: float,
    n_bins: int = 1000,
):
    """Gemiddelde ux per bin in een strook rond y0; terug: (x, z, ux, masker)."""
    sel = np.abs(centroids[:, 1] - y0) <= thickness / 2.0
    c = centroids[sel]
    ux = u_x[sel]
    if len(c) == 0:
        raise ValueError(
            f"geen cellen binnen de slice-strook |y - {y0}| <= {thickness / 2}"
        )
    x_edges = np.linspace(c[:, 0].min(), c[:, 0].max(), n_bins + 1)
    z_edges = np.linspace(c[:, 2].min(), c[:, 2].max(), n_bins + 1)
    counts, _, _ = np.histogram2d(c[:, 0], c[:, 2], bins=(x_edges, z_edges))
    sums, _, _ = np.histogram2d(
        c[:, 0], c[:, 2], bins=(x_edges, z_edges), weights=ux
    )
    with np.errstate(invalid="ignore"):
        grid = sums / counts
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
    """Schrijf de slice-figuur weg (luchtsnelheid in x-richting)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
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
        vmin=0.0,
        vmax=float(u_ref) * 1.05,
    )
    ax.set_xlabel("x [m]")
    ax.set_ylabel("z [m]")
    ax.set_title(f"{case_name}: luchtsnelheid in x-richting, slice y = {y0:g} m")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("ux [m/s]")
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)

"""Verwerk één OpenFoam-case: lees, bereken, schrijf output-custom vol.

De runner is de volledige route van versie 1 (plan-van-aanpak.md, sectie 8):
lees mesh en velden, bereken druk- en schuifkracht, CdA, frontaal
oppervlak en CD per atleetpatch en totaal, maak één slice-figuur en
schrijf alles naar een nieuwe map ``output-custom`` in de case-map, met
daarin een logbestand met fouten en de voortgang per stap.
"""

from __future__ import annotations

import csv
import logging
import os
import time

import numpy as np


def process_case(
    case_dir: str,
    time_dir: str | None = None,
    body_patches: tuple[str, ...] = ("pilot", "stoker"),
    rho: float = 1.225,
    u_ref: float | None = None,
    slice_y: float = 0.0,
    slice_thickness: float | None = None,
    output_name: str = "output-custom",
    overwrite: bool = False,
    frontal_dx: float = 0.002,
    slice_bins: int = 1000,
    slice_default_thickness: float = 0.02,
) -> dict:
    """Verwerk een case; geeft een samenvattingsdict terug.

    Fouten worden gelogd in het caselog en opnieuw ger-raisd, zodat de
    aanroeper (CLI) een duidelijke exitstatus kan geven.
    """
    case_dir = os.path.abspath(case_dir)
    case_name = os.path.basename(case_dir.rstrip("\\/"))
    t_start = time.perf_counter()

    # ---- output map en log -------------------------------------------------
    out_dir = os.path.join(case_dir, output_name)
    if os.path.exists(out_dir) and not overwrite:
        raise FileExistsError(
            f"{out_dir} bestaat al; gebruik --overwrite om erin te schrijven"
        )
    os.makedirs(out_dir, exist_ok=True)

    logfile = os.path.join(out_dir, f"{case_name}_postprocessing.log")
    log = logging.getLogger("cfd_postproc")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fh = logging.FileHandler(logfile, mode="a", encoding="utf-8")
    fh.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
    )
    log.addHandler(fh)
    log.info("start verwerking case %s", case_name)

    try:
        return _process_inner(
            case_dir, case_name, time_dir, body_patches, rho, u_ref,
            slice_y, slice_thickness, out_dir, overwrite, frontal_dx,
            slice_bins, t_start, logfile, slice_default_thickness,
        )
    except Exception:
        log.exception("verwerking mislukt")
        raise
    finally:
        log.info("einde verwerking na %.1f s", time.perf_counter() - t_start)
        for h in list(log.handlers):
            h.close()
            log.removeHandler(h)


def _process_inner(
    case_dir, case_name, time_dir, body_patches, rho, u_ref, slice_y,
    slice_thickness, out_dir, overwrite, frontal_dx, slice_bins, t_start, logfile,
    slice_default_thickness,
):
    from . import krachten, of_io, slice as slice_mod

    log = logging.getLogger("cfd_postproc")

    # ---- tijdmap en referentiesnelheid ------------------------------------
    if time_dir is None:
        time_dir = of_io.latest_time(case_dir)
    log.info("tijdmap: %s", time_dir)

    if u_ref is None:
        u_ref = of_io.read_variable(case_dir, "u_inlet")
    if u_ref is None:
        raise ValueError(
            "geen referredsnelheid: geen --u-ref gegeven en 'u_inlet' ontbreekt "
            "in system/Variables"
        )
    log.info("referentiesnelheid u_inlet = %s m/s", u_ref)

    # ---- mesh en velden -----------------------------------------------------
    t0 = time.perf_counter()
    mesh = of_io.read_mesh(case_dir)
    n_randfaces = sum(p.n_faces for p in mesh.patches)
    log.info(
        "mesh gelezen in %.1f s: %d punten, %d faces (%d intern, %d rand)",
        time.perf_counter() - t0, len(mesh.points), mesh.n_faces,
        mesh.n_faces - n_randfaces, n_randfaces,
    )

    t = os.path.join(case_dir, time_dir)
    p = of_io.read_internal_field(os.path.join(t, "p"))
    n_cells = len(p)
    log.info("p gelezen: %d cellen", n_cells)

    wss_patches = of_io.read_patch_values(
        os.path.join(t, "wallShearStress"), patch_names=list(body_patches)
    )
    # Gebruik UMean als beschikbaar (tijdsgemiddeld), anders U
    u_path = os.path.join(t, "UMean") if os.path.exists(os.path.join(t, "UMean")) else os.path.join(t, "U")
    u = of_io.read_internal_field(u_path)
    log.info("velden gelezen: p, wallShearStress, %s", os.path.basename(u_path))

    # ---- krachten en frontaal oppervlak ------------------------------------
    q = 0.5 * rho * u_ref**2  # dynamische druk
    patch_ids = {}
    for name in body_patches:
        try:
            patch_ids[name] = mesh.face_ids_of_patch(name)
        except KeyError:
            log.warning("patch '%s' niet gevonden: overgeslagen", name)
    if not patch_ids:
        raise ValueError(f"geen van de atleetpatches {body_patches} gevonden")

    per_patch = {}
    for name, ids in patch_ids.items():
        fp = krachten.pressure_drag(mesh, p, ids, rho)
        wss = wss_patches.get(name)
        if wss is None:
            log.warning(
                "geen wallShearStress-waarden voor patch '%s': schuifkracht 0", name
            )
            fs = np_zero3()
        else:
            if len(wss) != len(ids):
                raise ValueError(
                    f"wallShearStress op patch '{name}' heeft {len(wss)} faces, "
                    f"de mesh {len(ids)}: bestand en mesh passen niet"
                )
            fs = krachten.shear_drag(mesh, wss, ids, rho)
        per_patch[name] = {"druk": float(fp[0]), "schuif": float(fs[0])}

    frontal = krachten.frontal_area(mesh, patch_ids, dx=frontal_dx)
    log.info("frontaal oppervlak berekend (dx=%.4f m)", frontal_dx)

    for name, res in per_patch.items():
        res["weerstand"] = res["druk"] + res["schuif"]
        # CdA is onafhankelijk van het oppervlak; Cd gebruikt de eigen silhouette.
        res["frontaal"] = frontal[name]
        res["cda"] = res["weerstand"] / q
        res["cd"] = (
            res["weerstand"] / (q * res["frontaal"]) if res["frontaal"] > 0 else None
        )
        log.info(
            "patch %s: weerstand %.4g N (druk %.4g, schuif %.4g), "
            "frontaal %.4g m2, CdA %.4g m2, CD %.4g",
            name, res["weerstand"], res["druk"], res["schuif"], res["frontaal"],
            res["cda"], res["cd"] if res["cd"] is not None else float("nan"),
        )

    tot_druk = sum(r["druk"] for r in per_patch.values())
    tot_schuif = sum(r["schuif"] for r in per_patch.values())
    tot_weerstand = tot_druk + tot_schuif
    tot_frontaal = frontal["totaal"]
    tot_cda = tot_weerstand / q
    tot_cd = tot_weerstand / (q * tot_frontaal) if tot_frontaal > 0 else None
    log.info(
        "totaal: weerstand %.4g N, frontaal %.4g m2, CdA %.4g m2, CD %.4g",
        tot_weerstand, tot_frontaal, tot_cda, tot_cd if tot_cd is not None else float("nan"),
    )

    # ---- results.csv ---------------------------------------------------------
    csv_path = os.path.join(out_dir, "results.csv")
    _write_results(
        csv_path,
        per_patch,
        tot_druk,
        tot_schuif,
        tot_weerstand,
        tot_frontaal,
        tot_cda,
        tot_cd,
        rho,
        u_ref,
        log,
    )

    # ---- slice ---------------------------------------------------------------
    field_dir = os.path.join(case_dir, time_dir)
    centroids_t0 = time.perf_counter()
    # Gebruik de verbeterde cell_centers functie uit slice_mod
    centroids = slice_mod.cell_centers(mesh, log=log.info)
    log.info(
        "celzwaartepunten berekend in %.1f s",
        time.perf_counter() - centroids_t0,
    )

    if slice_thickness is None:
        slice_thickness = slice_default_thickness
    
    # Gebruik magnitude van snelheid in plaats van x-component
    u_mag = np.linalg.norm(u, axis=1)
    
    log.info("slice: y = %s, strookdikte %s m", slice_y, slice_thickness)
    png_path = os.path.join(out_dir, f"{case_name}_slice_y{slice_y:g}.png")
    slice_mod.make_slice_figure(
        cell_centers_arr=centroids,
        u_mag=u_mag,
        mesh_points=mesh.points,
        mesh_faces_offsets=mesh.face_offsets,
        mesh_faces_labels=mesh.face_verts,
        body_patch_names=body_patches,
        mesh_patches=mesh.patches,
        axis="y",
        pos=slice_y,
        tol=slice_thickness / 2.0,
        u_ref=u_ref,
        out_png=png_path,
        case_name=case_name,
        log=log.info,
    )
    log.info("slice-figuur: %s", os.path.basename(png_path))

    return {
        "output_dir": out_dir,
        "results_csv": csv_path,
        "slice_png": png_path,
        "log": logfile,
        "per_patch": per_patch,
        "totaal": {
            "weerstand": tot_weerstand,
            "frontaal": tot_frontaal,
            "cda": tot_cda,
            "cd": tot_cd,
        },
    }


def np_zero3():
    import numpy as np

    return np.zeros(3, dtype=np.float64)


def _write_results(
    csv_path, per_patch, tot_druk, tot_schuif, tot_weerstand, tot_frontaal,
    tot_cda, tot_cd, rho, u_ref, log,
):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "patch",
                "drukkracht_N",
                "schuifkracht_N",
                "weerstand_N",
                "frontaal_oppervlak_m2",
                "CD",
                "CdA_m2",
            ]
        )
        for name, r in per_patch.items():
            w.writerow(
                [
                    name,
                    f"{r['druk']:.6g}",
                    f"{r['schuif']:.6g}",
                    f"{r['weerstand']:.6g}",
                    f"{r['frontaal']:.6g}",
                    f"{r['cd']:.6g}" if r["cd"] is not None else "",
                    f"{r['cda']:.6g}",
                ]
            )
        w.writerow(
            [
                "totaal",
                f"{tot_druk:.6g}",
                f"{tot_schuif:.6g}",
                f"{tot_weerstand:.6g}",
                f"{tot_frontaal:.6g}",
                f"{tot_cd:.6g}" if tot_cd is not None else "",
                f"{tot_cda:.6g}",
            ]
        )
    log.info("results.csv geschreven met rho=%.4g kg/m3, u_ref=%.4g m/s", rho, u_ref)

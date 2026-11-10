"""CLI voor cfd_postproc: verwerk één OpenFOAM-case.

Voorbeeld:
    py -m src.cfd_postproc --case "pad/naar/Run_Tandem_027" [--time 1600]
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cfd_postproc",
        description=(
            "Lokale postprocessing van OpenFOAM RANS-cases van sporters: "
            "luchtweerstand, CdA, frontaal oppervlak, CD, slice-figuur en "
            "log, geschreven naar output-custom in de case-map."
        ),
    )
    parser.add_argument("--case", required=True, help="map van de simulatie")
    parser.add_argument(
        "--time", default=None, help="tijdmap; standaard de laatst geschreven tijd"
    )
    parser.add_argument(
        "--body-patches",
        default="pilot,stoker",
        help="komma-gescheiden wanden van de atleten (default: pilot,stoker)",
    )
    parser.add_argument("--rho", type=float, default=1.225, help="luchtdichtheid [kg/m3]")
    parser.add_argument(
        "--u-ref",
        type=float,
        default=None,
        help="referentiesnelheid [m/s]; standaard u_inlet uit system/Variables",
    )
    parser.add_argument(
        "--slice-y", type=float, default=0.0, help="slice-positie in y [m] (default 0)"
    )
    parser.add_argument(
        "--slice-thickness",
        type=float,
        default=None,
        help="strookdikte rond het slice-vlak [m] (default 0.02)",
    )
    parser.add_argument(
        "--output-dir",
        default="output-custom",
        help="naam van de uitvoermap in de case-map (default: output-custom)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="schrijf in een bestaande uitvoermap (bestanden worden overschreven)",
    )
    parser.add_argument(
        "--frontal-dx",
        type=float,
        default=0.002,
        help="rasterresolutie frontaal oppervlak [m] (default 0.002)",
    )
    parser.add_argument(
        "--slice-bins",
        type=int,
        default=1000,
        help="aantal bins van het slice-raster (default 1000)",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    from .case_runner import process_case

    try:
        result = process_case(
            case_dir=args.case,
            time_dir=args.time,
            body_patches=tuple(
                s.strip() for s in args.body_patches.split(",") if s.strip()
            ),
            rho=args.rho,
            u_ref=args.u_ref,
            slice_y=args.slice_y,
            slice_thickness=args.slice_thickness,
            output_name=args.output_dir,
            overwrite=args.overwrite,
            frontal_dx=args.frontal_dx,
            slice_bins=args.slice_bins,
        )
    except FileExistsError as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # logbestand bevat details en traceback
        print(f"FOUT: {exc} (details in het caselog)", file=sys.stderr)
        return 1

    print(f"Klaar. Output: {result['output_dir']}")
    print(f"  results.csv: {result['results_csv']}")
    print(f"  slice:       {result['slice_png']}")
    print(f"  log:         {result['log']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

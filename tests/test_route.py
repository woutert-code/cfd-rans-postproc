"""Unittests voor de volledige route (case_runner) en de CLI op de
fictieve mini-case: output-custom met results.csv, slice-figuur en log."""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from cfd_postproc import case_runner  # noqa: E402
from cfd_postproc.__main__ import main  # noqa: E402
from foam_fixture import StructuredCase  # noqa: E402

RHO = 1.225
U_REF = 16.0


class RouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    def make_case(self, name: str) -> str:
        case_dir = os.path.join(self.tmp.name, name)
        sc = StructuredCase(4, 3, 3, 0.1, 0.1, 0.1)
        sc.write(case_dir, time="2")
        return case_dir

    def test_volledige_route(self):
        self.case_dir = self.make_case("Run_Test_004a")
        result = case_runner.process_case(
            self.case_dir,
            body_patches=("pilot",),
            u_ref=U_REF,
            slice_y=0.05,
            slice_thickness=0.2,
            slice_bins=20,
        )
        out = result["output_dir"]
        self.assertTrue(os.path.isdir(out))
        for pad in (result["results_csv"], result["slice_png"], result["log"]):
            self.assertTrue(os.path.isfile(pad), pad)
            self.assertGreater(os.path.getsize(pad), 0)

        with open(result["results_csv"], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual({r["patch"] for r in rows}, {"pilot", "totaal"})

        # Druk + schuif op 0.04 m2 pijler vlak: kinematisch p=10, wss_x=0.5.
        q = 0.5 * RHO * U_REF**2
        verwacht = RHO * (10.0 + 0.5) * 0.04
        pilot = next(r for r in rows if r["patch"] == "pilot")
        self.assertAlmostEqual(float(pilot["weerstand_N"]), verwacht, delta=1e-6)
        self.assertAlmostEqual(float(pilot["frontaal_oppervlak_m2"]), 0.04, delta=0.002)
        self.assertAlmostEqual(float(pilot["CdA_m2"]), verwacht / q, delta=1e-6)
        # CD = CdA / A
        self.assertAlmostEqual(
            float(pilot["CD"]), verwacht / q / 0.04, delta=0.06
        )
        tot = next(r for r in rows if r["patch"] == "totaal")
        self.assertAlmostEqual(float(tot["weerstand_N"]), verwacht, delta=1e-6)

        # Log bevat minimaal start, tijdmap en einde.
        with open(result["log"], encoding="utf-8") as f:
            logtekst = f.read()
        self.assertIn("start verwerking", logtekst)
        self.assertIn("tijdmap", logtekst)
        self.assertIn("einde verwerking", logtekst)

    def test_bestande_map_geweigerd(self):
        case_dir = self.make_case("Run_Test_004b")
        out = os.path.join(case_dir, "output-custom")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "important.txt"), "w") as f:
            f.write("niet overschrijven")
        with self.assertRaises(FileExistsError):
            case_runner.process_case(
                case_dir,
                body_patches=("pilot",),
                u_ref=U_REF,
            )
        # de bestaande map blijft onaangetast
        self.assertTrue(os.path.isfile(os.path.join(out, "important.txt")))

    def test_cli(self):
        case_dir = self.make_case("Run_Test_004c")
        rc = main(["--case", case_dir, "--body-patches", "pilot",
                   "--u-ref", str(U_REF), "--slice-y", "0.05",
                   "--slice-thickness", "0.2", "--slice-bins", "20"])
        self.assertEqual(rc, 0)
        # nogmaals zonder --overwrite: geweigerd met exitcode 2
        rc = main(["--case", case_dir, "--body-patches", "pilot"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

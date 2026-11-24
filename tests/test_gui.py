"""Unittests voor de data-logica van het startscherm (gui.py) zonder display:
invoer parsing, build_kwargs, resultatentabel uit results.csv en de
extra_handlers van process_case (live log voor de GUI)."""

import logging
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from cfd_postproc import case_runner, gui  # noqa: E402
from cfd_postproc.__main__ import DEFAULT_SLICE_X  # noqa: E402
from foam_fixture import StructuredCase  # noqa: E402


class ParseTest(unittest.TestCase):
    def test_parse_positions_leeg_geeft_default(self):
        self.assertEqual(gui.parse_positions("", [0.0]), [0.0])
        self.assertEqual(gui.parse_positions("   ", [0.0]), [0.0])
        self.assertEqual(gui.parse_positions(None, [1.0, 2.0]), [1.0, 2.0])

    def test_parse_positions_lijst(self):
        self.assertEqual(gui.parse_positions("0.0, 0.5 , -1", [0.0]), [0.0, 0.5, -1.0])

    def test_parse_optional_float(self):
        self.assertIsNone(gui.parse_optional_float(""))
        self.assertIsNone(gui.parse_optional_float("  "))
        self.assertEqual(gui.parse_optional_float("16"), 16.0)

    def test_parse_optional_str(self):
        self.assertIsNone(gui.parse_optional_str(""))
        self.assertEqual(gui.parse_optional_str(" 1600 "), "1600")


class BuildKwargsTest(unittest.TestCase):
    def test_build_kwargs(self):
        kw = gui.build_kwargs(
            "C:\\pad\\naar\\case", "pilot, stoker", "1.225", "", "", "0.0", "", "0.05", True
        )
        self.assertEqual(kw["case_dir"], "C:\\pad\\naar\\case")
        self.assertEqual(kw["body_patches"], ("pilot", "stoker"))
        self.assertEqual(kw["rho"], 1.225)
        self.assertIsNone(kw["u_ref"])
        self.assertIsNone(kw["time_dir"])
        self.assertEqual(kw["slice_y"], [0.0])
        # leeg slice-x veld -> standaard uit de CLI (DEFAULT_SLICE_X)
        self.assertEqual(
            kw["slice_x"], [float(s) for s in DEFAULT_SLICE_X.split(",")]
        )
        self.assertEqual(kw["slice_thickness"], 0.05)
        self.assertTrue(kw["overwrite"])

    def test_build_kwargs_slice_x_ingevuld(self):
        kw = gui.build_kwargs("x", "pilot", "", "16", "1600", "0,0.5", "-1,2", "", False)
        self.assertEqual(kw["rho"], 1.225)  # leeg rho -> default
        self.assertEqual(kw["u_ref"], 16.0)
        self.assertEqual(kw["time_dir"], "1600")
        self.assertEqual(kw["slice_y"], [0.0, 0.5])
        self.assertEqual(kw["slice_x"], [-1.0, 2.0])
        self.assertIsNone(kw["slice_thickness"])
        self.assertFalse(kw["overwrite"])

    def test_build_kwargs_zonder_patches_is_fout(self):
        with self.assertRaises(ValueError):
            gui.build_kwargs("x", " , ", "1.225", "", "", "0", "0", "", False)


class ResultsTableTest(unittest.TestCase):
    def test_read_results_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = os.path.join(tmp, "Run_Test_005")
            sc = StructuredCase(4, 3, 3, 0.1, 0.1, 0.1)
            sc.write(case_dir, time="2")
            result = case_runner.process_case(
                case_dir,
                body_patches=("pilot",),
                u_ref=16.0,
                slice_y=0.05,
                slice_thickness=0.2,
                slice_bins=20,
            )
            headers, table = gui.read_results_table(result["results_csv"])
            # de vier gevraagde waarden uit het startscherm staan erin
            self.assertIn("weerstand [N]", headers)
            self.assertIn("frontaal oppervlak [m²]", headers)
            self.assertIn("CD", headers)
            self.assertIn("CdA [m²]", headers)
            patches = [row[0] for row in table]
            self.assertEqual(patches, ["pilot", "totaal"])
            cda = {row[0]: float(row[headers.index("CdA [m²]")]) for row in table}
            # één patch: CdA pilot == CdA totaal
            self.assertAlmostEqual(cda["pilot"], cda["totaal"], places=6)
            self.assertGreater(cda["pilot"], 0.0)


class ExtraHandlersTest(unittest.TestCase):
    def test_extra_handlers_ontvangen_logregels(self):
        records = []

        class ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        with tempfile.TemporaryDirectory() as tmp:
            case_dir = os.path.join(tmp, "Run_Test_006")
            sc = StructuredCase(4, 3, 3, 0.1, 0.1, 0.1)
            sc.write(case_dir, time="2")
            case_runner.process_case(
                case_dir,
                body_patches=("pilot",),
                u_ref=16.0,
                slice_y=0.05,
                slice_thickness=0.2,
                slice_bins=20,
                extra_handlers=[ListHandler()],
            )
        self.assertTrue(any("start verwerking" in r for r in records))
        self.assertTrue(any("einde verwerking" in r for r in records))


if __name__ == "__main__":
    unittest.main()

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


class BuildKwargsTest(unittest.TestCase):
    def test_default_slice_x_is_alleen_nul(self):
        # besluit 004: standaard x-slice = 0.0, net als y
        self.assertEqual(DEFAULT_SLICE_X, "0.0")

    def test_build_kwargs(self):
        kw = gui.build_kwargs("C:\\pad\\naar\\case", "0.0", "", True)
        self.assertEqual(kw["case_dir"], "C:\\pad\\naar\\case")
        self.assertEqual(kw["slice_y"], [0.0])
        # leeg slice-x veld -> standaard uit de CLI (DEFAULT_SLICE_X)
        self.assertEqual(
            kw["slice_x"], [float(s) for s in DEFAULT_SLICE_X.split(",")]
        )
        self.assertTrue(kw["overwrite"])
        # de verwijderde velden (patches, rho, u-ref, tijdmap, strookdikte)
        # worden niet doorgegeven: process_case gebruikt zijn defaults
        for sleutel in ("body_patches", "rho", "u_ref", "time_dir", "slice_thickness"):
            self.assertNotIn(sleutel, kw)

    def test_build_kwargs_slice_x_ingevuld(self):
        kw = gui.build_kwargs("x", "0,0.5", "-1,2", False)
        self.assertEqual(kw["slice_y"], [0.0, 0.5])
        self.assertEqual(kw["slice_x"], [-1.0, 2.0])
        self.assertFalse(kw["overwrite"])


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
            # de gevraagde waarden uit het startscherm staan erin
            self.assertIn("weerstand [N]", headers)
            self.assertIn("aandeel [%]", headers)
            self.assertIn("frontaal oppervlak [m²]", headers)
            self.assertIn("CD", headers)
            self.assertIn("CdA [m²]", headers)
            patches = [row[0] for row in table]
            self.assertEqual(patches, ["pilot", "totaal"])
            cda = {row[0]: float(row[headers.index("CdA [m²]")]) for row in table}
            # één patch: CdA pilot == CdA totaal
            self.assertAlmostEqual(cda["pilot"], cda["totaal"], places=6)
            self.assertGreater(cda["pilot"], 0.0)


class SliceNoteTest(unittest.TestCase):
    def test_slice_note_vermeldt_outputcustom_en_verbetering(self):
        # notitie in het startscherm: figuren naar output-custom + slice-
        # generatie wordt in een volgende versie verbeterd
        self.assertIn("output-custom", gui.SLICE_NOTE)
        self.assertIn("volgende versie", gui.SLICE_NOTE)


class PolymeshCheckTest(unittest.TestCase):
    def test_missing_polymesh_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = os.path.join(tmp, "Run_Test_007")
            StructuredCase(4, 3, 3, 0.1, 0.1, 0.1).write(case_dir, time="2")
            self.assertEqual(gui.missing_polymesh_files(case_dir), [])
            os.remove(os.path.join(case_dir, "constant", "polyMesh", "faces"))
            self.assertEqual(gui.missing_polymesh_files(case_dir), ["faces"])


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


class ComputeGeometryPayloadTest(unittest.TestCase):
    """compute_geometry_payload: gedeelde geometrieberekening (display-vrij)."""

    def test_polymesh_fallback_voor_fixturecase(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = os.path.join(tmp, "Run_Test_011")
            sc = StructuredCase(4, 3, 3, 0.1, 0.1, 0.1)
            sc.write(case_dir, time="2")
            payload, warns = gui.compute_geometry_payload(case_dir, ("pilot",))
        views, polys3d, bmin, bmax, n_total, n_3d, s, source, kleuren = payload
        self.assertEqual(set(views), {"front", "side", "top"})
        self.assertEqual(source, "polymesh")
        # polyMesh-fallback: één kleur voor alles (dict ontbreekt dan ook)
        self.assertIsNone(kleuren)
        self.assertGreater(n_total, 0)
        self.assertGreaterEqual(n_3d, 0)
        self.assertGreaterEqual(s, 1.0)
        self.assertEqual(len(warns), 1)
        self.assertIn("Geen STL-geometrie", warns[0])
        # elk van de drie views is een (mask, extent)-paar
        for mask, extent in views.values():
            self.assertTrue(hasattr(mask, "shape"))
            self.assertEqual(len(extent), 4)

    def test_stl_route_als_stls_beschikbaar(self):
        # volumetests blijven in test_geometrie_stl; hier alleen de ruilmelding
        with tempfile.TemporaryDirectory() as tmp:
            case_name = "Run_Test_012"
            stl_dir = os.path.join(tmp, "Mesh_Test_012", "constant", "triSurface")
            os.makedirs(stl_dir)
            # klein fictief binaire STL (dezelfde helper-logica, inline gehouden)
            import struct
            import numpy as np

            tris = np.array(
                [
                    [[0.4, 0.0, 0.0], [0.4, 0.2, 0.0], [0.4, 0.0, 0.2]],
                    [[0.4, 0.2, 0.0], [0.4, 0.2, 0.2], [0.4, 0.0, 0.2]],
                ],
                dtype="<f4",
            )
            p = os.path.join(stl_dir, "pilot.stl")
            with open(p, "wb") as f:
                f.write(b"\x00" * 80)
                f.write(struct.pack("<I", len(tris)))
                for t in tris:
                    f.write(np.zeros(3, dtype="<f4").tobytes())
                    f.write(t.tobytes())
                    f.write(struct.pack("<H", 0))
            case_dir = os.path.join(tmp, case_name)
            os.makedirs(case_dir)
            payload, warns = gui.compute_geometry_payload(case_dir, ("pilot",))
        self.assertEqual(payload[7], "stl")
        self.assertEqual(warns, [])
        # STL-route: per patch een eigen mask (dict) met de patch kleur
        views = payload[0]
        for v in ("front", "side", "top"):
            bodies, extent = views[v]
            self.assertEqual(set(bodies), {"pilot"})
            self.assertEqual(len(extent), 4)
        kleuren = payload[8]
        from cfd_postproc import geometrie
        self.assertEqual(set(kleuren), {geometrie.PATCH_COLORS["pilot"]})
        self.assertEqual(len(kleuren), payload[5])


if __name__ == "__main__":
    unittest.main()

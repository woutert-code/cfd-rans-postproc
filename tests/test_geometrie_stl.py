"""Unittests voor de STL-route in geometrie.py (display-vrij).

Volledig fictieve geometrie: een plat vlak uit twee driehoeken en een
tweede 'body' ernaast; geen relatie met echte atleten.
"""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402

from cfd_postproc import geometrie  # noqa: E402


def _write_binary_stl(path: str, tris: np.ndarray) -> None:
    tris = np.asarray(tris, dtype="<f4").reshape(-1, 3, 3)
    with open(path, "wb") as f:
        f.write(b"\x00" * 80)
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            f.write(np.zeros(3, dtype="<f4").tobytes())  # normaal (ongejkt)
            f.write(t.tobytes())
            f.write(struct.pack("<H", 0))


def _write_ascii_stl(path: str, tris: np.ndarray) -> None:
    tris = np.asarray(tris).reshape(-1, 3, 3)
    with open(path, "w") as f:
        f.write("solid vlak\n")
        for t in tris:
            f.write("  facet normal 0 0 0\n    outer loop\n")
            for v in t:
                f.write(f"      vertex {v[0]} {v[1]} {v[2]}\n")
            f.write("    endloop\n  endfacet\n")
        f.write("endsolid vlak\n")


def _vierkant() -> np.ndarray:
    """Plat vlak x = 0.4, 0.2 x 0.2 m, uit twee driehoeken."""
    return np.array(
        [
            [[0.4, 0.0, 0.0], [0.4, 0.2, 0.0], [0.4, 0.0, 0.2]],
            [[0.4, 0.2, 0.0], [0.4, 0.2, 0.2], [0.4, 0.0, 0.2]],
        ]
    )


def _vierkant_y() -> np.ndarray:
    """Plat vlak y = 0.5 (verschillende 'patch'), 0.2 x 0.2 m."""
    return np.array(
        [
            [[0.0, 0.5, 0.0], [0.2, 0.5, 0.0], [0.0, 0.5, 0.2]],
            [[0.2, 0.5, 0.0], [0.2, 0.5, 0.2], [0.0, 0.5, 0.2]],
        ]
    )


def _schrijf_bodies(root: str) -> str:
    """Maak <root>/Mesh_Test_Tri/constant/triSurface met pilot.stl en stoker.stl."""
    stl_dir = os.path.join(root, "Mesh_Test_Tri", "constant", "triSurface")
    os.makedirs(stl_dir)
    _write_binary_stl(os.path.join(stl_dir, "pilot.stl"), _vierkant())
    _write_ascii_stl(os.path.join(stl_dir, "stoker.stl"), _vierkant_y())
    return stl_dir


class TestReadStl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin_path = os.path.join(self.tmp.name, "pilot.stl")
        self.ascii_path = os.path.join(self.tmp.name, "stoker.stl")
        _write_binary_stl(self.bin_path, _vierkant())
        _write_ascii_stl(self.ascii_path, _vierkant_y())

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_stl_binaire_roundtrip(self):
        tris = geometrie.read_stl(self.bin_path)
        self.assertEqual(tris.shape, (2, 3, 3))
        self.assertTrue(np.allclose(tris, _vierkant(), atol=1e-5))

    def test_read_stl_ascii_roundtrip(self):
        tris = geometrie.read_stl(self.ascii_path)
        self.assertEqual(tris.shape, (2, 3, 3))
        self.assertTrue(np.allclose(tris, _vierkant_y(), atol=1e-5))

    def test_read_stl_onzin_is_fout(self):
        path = os.path.join(self.tmp.name, "kapot.stl")
        with open(path, "wb") as f:
            f.write(b"dit is geen STL-bestand")
        with self.assertRaises(ValueError):
            geometrie.read_stl(path)


class TestFindStlDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_nil_geen_stl(self):
        case = os.path.join(self.tmp.name, "Run_Zonder")
        os.makedirs(case)
        self.assertIsNone(geometrie.find_stl_dir(case))

    def test_binnen_de_case(self):
        case = os.path.join(self.tmp.name, "Run_Test_Tri")
        stl_dir = os.path.join(case, "constant", "triSurface")
        os.makedirs(stl_dir)
        _write_binary_stl(os.path.join(stl_dir, "pilot.stl"), _vierkant())
        self.assertEqual(geometrie.find_stl_dir(case), stl_dir)

    def test_broer_zus_mesh_map(self):
        _schrijf_bodies(self.tmp.name)
        case = os.path.join(self.tmp.name, "Run_Test_Tri")
        os.makedirs(case)
        stl_dir = os.path.join(self.tmp.name, "Mesh_Test_Tri", "constant", "triSurface")
        self.assertEqual(geometrie.find_stl_dir(case), stl_dir)

    def test_afzonderlijke_case_en_mesh_map(self):
        # structuur <root>/Case/Run_X en <root>/Mesh/Mesh_X (bv. E:\KNWU CFD)
        _schrijf_bodies(self.tmp.name)
        mesh_root = os.path.join(self.tmp.name, "Mesh")
        os.makedirs(mesh_root)
        os.rename(
            os.path.join(self.tmp.name, "Mesh_Test_Tri"),
            os.path.join(mesh_root, "Mesh_Test_Tri"),
        )
        case = os.path.join(self.tmp.name, "Case", "Run_Test_Tri")
        os.makedirs(case)
        stl_dir = os.path.join(mesh_root, "Mesh_Test_Tri", "constant", "triSurface")
        self.assertEqual(geometrie.find_stl_dir(case), stl_dir)


class TestReadBodyTriangles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        _schrijf_bodies(self.tmp.name)
        self.case = os.path.join(self.tmp.name, "Run_Test_Tri")
        os.makedirs(self.case)

    def tearDown(self):
        self.tmp.cleanup()

    def test_beide_patches_gevonden(self):
        tris_map = geometrie.read_body_triangles(self.case, ("pilot", "stoker"))
        self.assertIsNotNone(tris_map)
        self.assertIn("pilot", tris_map)
        self.assertTrue(np.allclose(tris_map["pilot"], _vierkant(), atol=1e-5))
        self.assertTrue(np.allclose(tris_map["stoker"], _vierkant_y(), atol=1e-5))

    def test_ontbrekende_patch_geeft_none(self):
        # alleen een 'anderesthetic.stl' in de triSurface-map
        stl_dir = os.path.join(self.tmp.name, "Mesh_Test_Tri", "constant", "triSurface")
        os.remove(os.path.join(stl_dir, "stoker.stl"))
        self.assertIsNone(geometrie.read_body_triangles(self.case, ("pilot", "stoker")))

    def test_geen_stl_map_geeft_none(self):
        leeg = os.path.join(self.tmp.name, "Run_Ander")
        os.makedirs(leeg)
        self.assertIsNone(geometrie.read_body_triangles(leeg, ("pilot",)))


class TestViewsEnDecimatie(unittest.TestCase):
    def setUp(self):
        self.all_tris = np.concatenate([_vierkant(), _vierkant_y()])

    def test_bounding_box_triangles(self):
        bmin, bmax = geometrie.bounding_box_triangles(self.all_tris)
        self.assertAlmostEqual(float(bmin[0]), 0.0, places=5)
        self.assertAlmostEqual(float(bmax[0]), 0.4, places=5)
        self.assertAlmostEqual(float(bmin[1]), 0.0, places=5)
        self.assertAlmostEqual(float(bmax[1]), 0.5, places=5)
        self.assertAlmostEqual(float(bmin[2]), 0.0, places=5)
        self.assertAlmostEqual(float(bmax[2]), 0.2, places=5)

    def test_raster_view_triangles_solid(self):
        dx = 0.005
        mask, extent = geometrie.raster_view_triangles(_vierkant(), "front", dx=dx)
        # vlak x=0.4: front-view is het y-z vlak -> 0.2 x 0.2 m = 40x40 pixels
        self.assertEqual(mask.shape[0], 40 + 2)
        self.assertAlmostEqual(float(mask.sum()) * dx * dx, 0.04, delta=0.005)

    def test_decimate_triangles_limiet_en_inflatie(self):
        # veel kleine driehoeken over 1x1x1 -> decimeren tot <= 50
        rng = np.random.default_rng(42)
        n = 4000
        p = rng.random((n, 3, 3)) * 1.0
        tris = p.astype(np.float32)
        sel, h, s = geometrie.decimate_triangles(tris, max_polys=50, start_h=0.01)
        self.assertLessEqual(len(sel), 50)
        self.assertGreater(h, 0.01)
        self.assertGreaterEqual(s, 1.0)
        self.assertLessEqual(s, geometrie.DEFAULT_MAX_INFLATE)
        # h verdubbelt; s = h / gemiddelde diameter, dus s <= h kleine getallen
        self.assertGreater(h, 0.0)

    def test_decimate_triangles_plat_vlak(self):
        # volumepunt cloud in een plat vlak: min == max op een as mag niet crashen
        sel, h, s = geometrie.decimate_triangles(_vierkant(), max_polys=10_000)
        self.assertEqual(len(sel), 2)

    def test_raster_view_triangles_extent_gelijk_rooster(self):
        # zelfde extent -> zelfde roosterafmetingen, zodat de per-patch masks
        # over elkaar getekend kunnen worden
        dx = 0.005
        _, ext = geometrie.raster_view_triangles(self.all_tris, "top", dx=dx)
        m1, e1 = geometrie.raster_view_triangles(_vierkant(), "top", dx=dx, extent=ext)
        m2, e2 = geometrie.raster_view_triangles(_vierkant_y(), "top", dx=dx, extent=ext)
        self.assertEqual(e1, e2)
        self.assertEqual(m1.shape, m2.shape)

    def test_make_view_figure_kleur_per_patch(self):
        from matplotlib.colors import to_rgb

        dx = 0.005
        _, ext = geometrie.raster_view_triangles(self.all_tris, "top", dx=dx)
        m_stoker = geometrie.raster_view_triangles(
            _vierkant(), "top", dx=dx, extent=ext
        )[0]
        m_pilot = geometrie.raster_view_triangles(
            _vierkant_y(), "top", dx=dx, extent=ext
        )[0]
        fig = geometrie.make_view_figure(
            "top", {"pilot": m_pilot, "stoker": m_stoker}, ext
        )
        arr = fig.axes[0].images[0].get_array()
        self.assertEqual(arr.shape, m_pilot.shape + (4,))
        alleen_pilot = m_pilot & ~m_stoker
        alleen_stoker = m_stoker & ~m_pilot
        self.assertGreater(alleen_pilot.sum(), 0)
        self.assertGreater(alleen_stoker.sum(), 0)
        self.assertTrue(
            np.allclose(
                arr[alleen_pilot][:, :3],
                to_rgb(geometrie.PATCH_COLORS["pilot"]),
            )
        )
        self.assertTrue(
            np.allclose(
                arr[alleen_stoker][:, :3],
                to_rgb(geometrie.PATCH_COLORS["stoker"]),
            )
        )
        self.assertTrue(np.all(arr[alleen_pilot][:, 3] == 1.0))
        self.assertTrue(np.all(arr[~(m_pilot | m_stoker)][:, 3] == 0.0))


class TestKleurenPerPatch(unittest.TestCase):
    def test_patch_colors_pilot_licht_stoker_onveranderd(self):
        # stoker exact de oude "Blues"-kleur van de samengevoegde silhouette
        self.assertEqual(geometrie.PATCH_COLORS["stoker"], "#08306b")
        pilot = geometrie.PATCH_COLORS["pilot"]
        stoker = geometrie.PATCH_COLORS["stoker"]
        # pilot: duidelijk lichter (veel hogere roodwaarde) en herkenbaar blauw
        self.assertGreater(int(pilot[1:3], 16), 90)
        self.assertGreater(int(pilot[3:5], 16), 90)
        self.assertGreater(int(pilot[5:7], 16), int(pilot[1:3], 16) + 30)
        self.assertLess(int(stoker[1:3], 16), 20)


if __name__ == "__main__":
    unittest.main()

"""Unittests voor geometrie.py (display-vrij): body-face selectie, bounding box,
PIL-raster van de 2D-views (solid), cel-decimatie voor de 3D en de figures."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402

from cfd_postproc import geometrie, of_io  # noqa: E402
from foam_fixture import StructuredCase  # noqa: E402


class GeometrieTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.case_dir = os.path.join(cls.tmp.name, "Run_Test_010")
        cls.sc = StructuredCase(4, 3, 3, 0.1, 0.1, 0.1)
        cls.sc.write(cls.case_dir, time="2")
        cls.mesh = of_io.read_mesh(cls.case_dir)
        cls.ids = geometrie.body_face_ids(cls.mesh, ("pilot",))


class TestBodyFaces(GeometrieTestBase):
    def test_body_face_ids_pilot(self):
        pilot = next(p for p in self.mesh.patches if p.name == "pilot")
        self.assertEqual(len(self.ids), pilot.n_faces)
        self.assertGreaterEqual(int(self.ids.min()), pilot.start_face)
        self.assertLess(int(self.ids.max()), pilot.start_face + pilot.n_faces)

    def test_body_face_ids_onbekende_patch_is_fout(self):
        with self.assertRaises(ValueError):
            geometrie.body_face_ids(self.mesh, ("bestaat_niet",))

    def test_bounding_box_pilot_op_x_max_vlak(self):
        bmin, bmax = geometrie.bounding_box(self.mesh, self.ids)
        # pilot zit op het x = 0.4 vlak; body_set dekt j,k in 0..1 -> y/z in 0..0.2
        self.assertAlmostEqual(float(bmin[0]), 0.4, places=5)
        self.assertAlmostEqual(float(bmax[0]), 0.4, places=5)
        self.assertAlmostEqual(float(bmin[1]), 0.0, places=5)
        self.assertAlmostEqual(float(bmax[1]), 0.2, places=5)
        self.assertAlmostEqual(float(bmin[2]), 0.0, places=5)
        self.assertAlmostEqual(float(bmax[2]), 0.2, places=5)

    def test_sizes_text(self):
        bmin = np.array([0.4, 0.0, 0.0])
        bmax = np.array([0.4, 0.3, 0.3])
        txt = geometrie.sizes_text(bmin, bmax)
        self.assertIn("Lengte (x): 0.000 m", txt)
        self.assertIn("Breedte (y): 0.300 m", txt)
        self.assertIn("Hoogte (z): 0.300 m", txt)

    def test_face_centroids_of(self):
        cents = geometrie.face_centroids_of(self.mesh, self.ids)
        self.assertEqual(cents.shape, (len(self.ids), 3))
        # alle pilot-faces liggen op x = 0.4
        self.assertTrue(np.allclose(cents[:, 0], 0.4, atol=1e-5))


class TestRasterView(GeometrieTestBase):
    def test_raster_front_is_solid_en_heeft_oppervlak(self):
        dx = 0.005
        mask, extent = geometrie.raster_view(self.mesh, self.ids, "front", dx=dx)
        # pilot-oppervlak = 0.2 x 0.2 m = 0.04 m2 (4 quads op het x=0.4 vlak)
        opp = float(mask.sum()) * dx * dx
        self.assertAlmostEqual(opp, 0.04, delta=0.005)
        # extent dekt y/z in 0..0.2 (+ marge)
        self.assertAlmostEqual(extent[0], 0.0, places=5)
        self.assertGreater(extent[1], 0.2)
        self.assertAlmostEqual(extent[2], 0.0, places=5)
        self.assertGreater(extent[3], 0.2)

    def test_raster_top_heeft_x_as(self):
        # bovenaanzicht: horizontale as is x; pilot is plat in x (0.4..0.4+marge)
        mask, extent = geometrie.raster_view(self.mesh, self.ids, "top", dx=0.01)
        self.assertLess(extent[1] - extent[0], 0.05)  # smal in x
        self.assertGreater(extent[3] - extent[2], 0.15)  # breed in y


class TestDecimate(GeometrieTestBase):
    def test_decimate_bij_klein_aantal_allemaal(self):
        out, h = geometrie.decimate_surface(self.mesh, self.ids, max_polys=100)
        self.assertEqual(len(out), len(self.ids))
        self.assertGreater(h, 0)

    def test_decimate_voldoet_aan_limiet_en_subset(self):
        out, h = geometrie.decimate_surface(self.mesh, self.ids, max_polys=2)
        self.assertLessEqual(len(out), 2)
        self.assertTrue(set(out.tolist()) <= set(self.ids.tolist()))

    def test_polygons_of_vorm(self):
        polys = geometrie.polygons_of(self.mesh, self.ids)
        self.assertEqual(len(polys), len(self.ids))
        for p in polys:
            self.assertEqual(p.shape[1], 3)
            self.assertEqual(p.shape[0], 4)  # quads in de fixture

    def test_inflation_factor(self):
        # fixture-faces zijn 0.1 m quads (diameter ~0.113 m)
        # cel kleiner dan face -> geen inflatie
        self.assertEqual(geometrie.inflation_factor(self.mesh, self.ids, 0.05), 1.0)
        # cel veel groter dan face -> afgekapt op max_s
        self.assertEqual(
            geometrie.inflation_factor(self.mesh, self.ids, 1.0), geometrie.DEFAULT_MAX_INFLATE
        )

    def test_inflate_polygons_schaalt_rond_zwaartepunt(self):
        quad = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]])
        out = geometrie.inflate_polygons([quad], 2.0)[0]
        # zwaartepunt blijft (0.5, 0.5, 0), spreiding verdubbelt
        self.assertTrue(np.allclose(out.mean(axis=0), quad.mean(axis=0)))
        self.assertAlmostEqual(float(out[:, 0].max() - out[:, 0].min()), 2.0)
        # s <= 1 -> ongewijzigd
        self.assertIs(geometrie.inflate_polygons([quad], 1.0)[0], quad)


class TestFigures(GeometrieTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bmin, cls.bmax = geometrie.bounding_box(cls.mesh, cls.ids)
        cls.mask, cls.extent = geometrie.raster_view(cls.mesh, cls.ids, "front", dx=0.01)
        cls.polys = geometrie.polygons_of(cls.mesh, cls.ids)

    def test_view_figuur_front(self):
        fig = geometrie.make_view_figure("front", self.mask, self.extent)
        ax = fig.axes[0]
        self.assertIn("Vooraanzicht", ax.get_title())
        self.assertEqual(ax.get_xlabel(), "y [m]")
        self.assertEqual(ax.get_ylabel(), "z [m]")
        self.assertEqual(len(ax.images), 1)  # solid raster, geen point cloud

    def test_view_figuur_side_en_top(self):
        for view, xlabel, ylabel in (("side", "x [m]", "z [m]"), ("top", "x [m]", "y [m]")):
            m, e = geometrie.raster_view(self.mesh, self.ids, view, dx=0.01)
            fig = geometrie.make_view_figure(view, m, e)
            ax = fig.axes[0]
            self.assertEqual(ax.get_xlabel(), xlabel)
            self.assertEqual(ax.get_ylabel(), ylabel)

    def test_3d_figuur(self):
        fig = geometrie.make_3d_figure(self.polys, self.bmin, self.bmax)
        ax = fig.axes[0]
        self.assertEqual(ax.name, "3d")
        self.assertEqual(len(ax.collections), 1)
        self.assertIn("3D", ax.get_title())


class TestRasterViewIndex(GeometrieTestBase):
    def test_index_beeld_op_fixture(self):
        dx = 0.005
        idx, extent = geometrie.raster_view_index(self.mesh, self.ids, "front", dx=dx)
        vals = idx[idx >= 0]
        self.assertGreater(vals.size, 0)
        # indexen zijn rijnummers in face_ids
        self.assertTrue(set(vals.tolist()) <= set(range(len(self.ids))))
        #zelfde dekking als het bool-masker van raster_view
        opp = float((idx >= 0).sum()) * dx * dx
        self.assertAlmostEqual(opp, 0.04, delta=0.005)
        self.assertEqual(len(extent), 4)

    def test_painter_dichtstbijzijnde_face_wint(self):
        # synthetische mesh: twee quads met dezelfde y-z-projectie, op x=0 en x=1
        pts = np.array(
            [
                [0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 1.0], [1.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )
        mesh = of_io.FoamMesh(
            pts,
            np.array([0, 4, 8], dtype=np.int32),
            np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.int32),
            np.array([0, 0], dtype=np.int32),
            np.array([], dtype=np.int32),
            [],
        )
        ids = np.array([0, 1])  # face 0 op x=0, face 1 op x=1
        idx, _extent = geometrie.raster_view_index(mesh, ids, "front", dx=0.1)
        # front-camera kijkt vanaf -x: face 0 (x=0) is het dichtstbij en wint
        vals = idx[idx >= 0]
        self.assertGreater(vals.size, 0)
        self.assertTrue((vals == 0).all())

    def test_gemixte_driehoeken_en_quads(self):
        # regressie: faces met verschillend vertexaantal (3 en 4, zoals in
        # een echte polyMesh) mogen niet crashen op np.concatenate
        pts = np.array(
            [
                [0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0],  # driehoek
                [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 1.0], [1.0, 0.0, 1.0],  # quad
            ],
            dtype=np.float32,
        )
        mesh = of_io.FoamMesh(
            pts,
            np.array([0, 3, 7], dtype=np.int32),
            np.array([0, 1, 2, 3, 4, 5, 6], dtype=np.int32),
            np.array([0, 0], dtype=np.int32),
            np.array([], dtype=np.int32),
            [],
        )
        ids = np.array([0, 1])
        for view in ("front", "side", "top"):
            idx, extent = geometrie.raster_view_index(mesh, ids, view, dx=0.1)
            self.assertGreater((idx >= 0).sum(), 0)
            self.assertEqual(len(extent), 4)
            vals = idx[idx >= 0]
            self.assertTrue(set(vals.tolist()) <= {0, 1})

    def test_cp_image_from_index(self):
        idx = np.array([[-1, 0], [1, -1]], dtype=np.int32)
        img = geometrie.cp_image_from_index(
            idx, np.array([2.0, 3.0], dtype=np.float32)
        )
        self.assertTrue(np.isnan(img[0, 0]))
        self.assertEqual(float(img[0, 1]), 2.0)
        self.assertEqual(float(img[1, 0]), 3.0)
        self.assertTrue(np.isnan(img[1, 1]))


class TestCpFigure(GeometrieTestBase):
    def test_cp_figuur_heeft_beeld_en_colorbar(self):
        idx, extent = geometrie.raster_view_index(self.mesh, self.ids, "front", dx=0.01)
        cp_img = geometrie.cp_image_from_index(
            idx, np.full(len(self.ids), 0.5, dtype=np.float32)
        )
        fig = geometrie.make_cp_view_figure("front", cp_img, extent)
        ax = fig.axes[0]
        self.assertEqual(len(ax.images), 1)
        self.assertIn("Cp", ax.get_title())
        self.assertEqual(ax.get_xlabel(), "y [m]")
        self.assertEqual(ax.get_ylabel(), "z [m]")
        # colorbar op een tweede as; symmetrische schaal rond 0
        self.assertEqual(len(fig.axes), 2)
        self.assertEqual(tuple(ax.images[0].get_clim()), (-0.5, 0.5))

    def test_cp_figuur_met_expliciet_bereik(self):
        # besluit 010: vast bereik -2 t/m 1 (vmin/vmax doorgegeven)
        idx, extent = geometrie.raster_view_index(self.mesh, self.ids, "front", dx=0.01)
        cp_img = geometrie.cp_image_from_index(
            idx, np.full(len(self.ids), 5.0, dtype=np.float32)  # buiten bereik
        )
        fig = geometrie.make_cp_view_figure(
            "front", cp_img, extent, vmin=-2.0, vmax=1.0
        )
        self.assertEqual(tuple(fig.axes[0].images[0].get_clim()), (-2.0, 1.0))

    def test_cp_figuur_zonder_titel_voor_ingebouwd_panel(self):
        idx, extent = geometrie.raster_view_index(self.mesh, self.ids, "top", dx=0.01)
        cp_img = geometrie.cp_image_from_index(
            idx, np.full(len(self.ids), -0.25, dtype=np.float32)
        )
        fig = geometrie.make_cp_view_figure(
            "top", cp_img, extent, figsize=(3.1, 2.5), with_title=False
        )
        self.assertEqual(fig.axes[0].get_title(), "")
        self.assertEqual(fig.axes[0].get_xlabel(), "x [m]")


if __name__ == "__main__":
    unittest.main()

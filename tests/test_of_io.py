"""Unittests voor src/cfd_postproc/of_io.py op een fictieve mini-case."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402

from cfd_postproc import of_io  # noqa: E402
from foam_fixture import StructuredCase  # noqa: E402

DX, DY, DZ = 0.1, 0.1, 0.1


class MiniCaseTestBase(unittest.TestCase):
    nx, ny, nz = 4, 3, 3

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.case_dir = os.path.join(cls.tmp.name, "Run_Test_001")
        cls.sc = StructuredCase(cls.nx, cls.ny, cls.nz, DX, DY, DZ)
        cls.sc.write(cls.case_dir, time="2")


class TestMeshReading(MiniCaseTestBase):
    def setUp(self):
        self.mesh = of_io.read_mesh(self.case_dir)

    def test_puntenaantal_en_coordinaten(self):
        self.assertEqual(len(self.mesh.points), (self.nx + 1) * (self.ny + 1) * (self.nz + 1))

    def test_faceconsistentie(self):
        sc = self.sc
        self.assertEqual(self.mesh.n_faces, len(sc.faces))
        self.assertEqual(len(self.mesh.face_verts), sum(len(v) for v in sc.faces))
        self.assertEqual(len(self.mesh.owner), len(sc.faces))

    def test_patches(self):
        namen = {p.name: p for p in self.mesh.patches}
        self.assertIn("pilot", namen)
        self.assertIn("inlet", namen)
        self.assertEqual(namen["pilot"].n_faces, len(self.sc.body_jk))
        totale_randfaces = sum(p.n_faces for p in self.mesh.patches)
        self.assertEqual(
            totale_randfaces,
            2 * self.ny * self.nz + 2 * self.nx * self.nz + 2 * self.nx * self.ny,
        )

    def test_eerste_face_vertices(self):
        # Interne x-face i=1, j=0, k=0 heeft verwachte hoekpunten.
        p = self.sc.point_ids
        eerste = of_io.FoamMesh.face_ids_of_patch  # slechts aanwezigheidscheck
        ids = self.mesh.face_ids_of_patch("pilot")
        self.assertTrue(len(ids) > 0)
        v0 = self.mesh.face_verts[
            self.mesh.face_offsets[ids[0]] : self.mesh.face_offsets[ids[0] + 1]
        ]
        self.assertEqual(len(v0), 4)


class TestFieldReading(MiniCaseTestBase):
    def test_p_internal(self):
        p = of_io.read_internal_field(os.path.join(self.case_dir, "2", "p"))
        self.assertEqual(len(p), self.nx * self.ny * self.nz)
        self.assertTrue(np.allclose(p, 10.0))

    def test_u_internal_vector(self):
        u = of_io.read_internal_field(os.path.join(self.case_dir, "2", "U"))
        self.assertEqual(u.shape, (self.nx * self.ny * self.nz, 3))
        self.assertTrue(np.allclose(u[:, 0], 16.0))

    def test_wss_patch_waarden(self):
        vals = of_io.read_patch_values(
            os.path.join(self.case_dir, "2", "wallShearStress")
        )
        self.assertIn("pilot", vals)
        n_pilot = next(p.n_faces for p in self.mesh_patches() if p.name == "pilot")
        self.assertEqual(vals["pilot"].shape, (n_pilot, 3))
        self.assertTrue(np.allclose(vals["pilot"][:, 0], 0.5))

    def mesh_patches(self):
        boundary = of_io.read_boundary(
            os.path.join(self.case_dir, "constant", "polyMesh", "boundary")
        )
        return boundary


class TestVariablesEnTijd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.case_dir = os.path.join(cls.tmp.name, "Run_Test_002")
        sc = StructuredCase(2, 2, 2, 0.1, 0.1, 0.1)
        sc.write(cls.case_dir, time="5")

    def test_u_inlet(self):
        self.assertAlmostEqual(of_io.read_variable(self.case_dir, "u_inlet"), 16.0)

    def test_latest_time(self):
        self.assertEqual(of_io.latest_time(self.case_dir), "5")


if __name__ == "__main__":
    unittest.main()

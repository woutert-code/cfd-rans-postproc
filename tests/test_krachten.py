"""Unittests voor src/cfd_postproc/krachten.py op de fictieve mini-case."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402

from cfd_postproc import krachten, of_io  # noqa: E402
from foam_fixture import StructuredCase  # noqa: E402

RHO = 1.225
DX = 0.1  # celafmeting in de fixture


class KrachtenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.case_dir = os.path.join(cls.tmp.name, "Run_Test_003")
        cls.sc = StructuredCase(4, 3, 3, DX, DX, DX)
        cls.sc.write(cls.case_dir, time="2")
        cls.mesh = of_io.read_mesh(cls.case_dir)
        cls.p = of_io.read_internal_field(os.path.join(cls.case_dir, "2", "p"))
        ids = cls.mesh.face_ids_of_patch("pilot")
        cls.pilot_ids = ids
        cls.n_pilot_faces = len(ids)

    def test_sf_op_atleetfaces(self):
        sf, cen = krachten.face_geometry(self.mesh, self.pilot_ids)
        self.assertEqual(sf.shape, (self.n_pilot_faces, 3))
        # Elke pilot-face is een 0.1x0.1 kwadraat met normaal +x.
        self.assertTrue(np.allclose(np.linalg.norm(sf, axis=1), DX * DX))
        self.assertTrue(np.allclose(sf[:, 0], DX * DX))
        self.assertTrue(np.allclose(sf[:, 1:], 0.0))

    def test_drukkracht(self):
        f = krachten.pressure_drag(self.mesh, self.p, self.pilot_ids, RHO)
        opp = self.n_pilot_faces * DX * DX
        self.assertAlmostEqual(f[0], RHO * 10.0 * opp, delta=1e-7)
        self.assertAlmostEqual(f[1], 0.0, delta=1e-8)
        self.assertAlmostEqual(f[2], 0.0, delta=1e-8)

    def test_schuifkracht(self):
        wss = of_io.read_patch_values(
            os.path.join(self.case_dir, "2", "wallShearStress"),
            patch_names=["pilot"],
        )["pilot"]
        f = krachten.shear_drag(self.mesh, wss, self.pilot_ids, RHO)
        opp = self.n_pilot_faces * DX * DX
        # SHEAR_SIGN is -1 (tractie tegengesteld aan de wandnormaal);
        # gecontroleerd op de echte voorbeeldcase, zie krachten.py.
        self.assertAlmostEqual(f[0], krachten.SHEAR_SIGN * RHO * 0.5 * opp, delta=1e-8)
        self.assertAlmostEqual(f[1], 0.0, delta=1e-8)
        self.assertAlmostEqual(f[2], 0.0, delta=1e-8)

    def test_frontaal_oppervlak(self):
        gebieden = krachten.frontal_area(
            self.mesh, {"pilot": self.pilot_ids}, dx=0.002
        )
        # Silhouette van 2x2 cellen van 0.1 m: 0.04 m2.
        self.assertAlmostEqual(gebieden["pilot"], 0.04, delta=0.002)
        self.assertAlmostEqual(gebieden["totaal"], 0.04, delta=0.002)


if __name__ == "__main__":
    unittest.main()

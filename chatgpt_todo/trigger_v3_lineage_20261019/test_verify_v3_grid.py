"""Hostile synthetic checks for pinned 4x5 projection only."""
from __future__ import annotations
import unittest
from verify_v3_grid import ROWS,verify

class FrozenSourceTests(unittest.TestCase):
    def test_reference_and_all_grid_cells(self):
        result=verify()
        self.assertEqual(result['grid_cells'],20)
        self.assertEqual(result['v3_joint']['hardware_only'],195)
        self.assertEqual(result['scientific_release'],'NOT_AUTHORIZED')
    def test_row_permutation_invariant(self):
        self.assertEqual(verify(ROWS),verify(ROWS[::-1]))
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):verify(ROWS[:-1]+(ROWS[0],))
    def test_missing_rejected(self):
        with self.assertRaises(ValueError):verify(ROWS[:-1])
    def test_bad_margin_rejected(self):
        r=list(ROWS);z=list(r[0]);z[6]+=1;r[0]=tuple(z)
        with self.assertRaises(ValueError):verify(tuple(r))
    def test_fabricated_zero_hardware_rejected(self):
        r=list(ROWS);z=list(r[7]);z[6]=0;r[7]=tuple(z)
        with self.assertRaises(ValueError):verify(tuple(r))
    def test_noninteger_rejected(self):
        r=list(ROWS);z=list(r[0]);z[2]=165.0;r[0]=tuple(z)
        with self.assertRaises(ValueError):verify(tuple(r))
    def test_same_marginals_do_not_prove_event_identity(self):
        a=(1,0,1,0);b=(0,1,0,1)
        self.assertEqual(sum(a),sum(b))
        self.assertEqual(sum(x and y for x,y in zip(a,b)),0)
if __name__=='__main__':unittest.main()

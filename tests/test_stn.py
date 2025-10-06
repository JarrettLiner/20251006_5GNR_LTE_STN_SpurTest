# tests/test_stn.py
import unittest
from measurements.SubThermalNoise import option_functions
class TestSTN(unittest.TestCase):
    def test_sweep_noise_mkr(self):
        instr = option_functions(freq=6e9)
        marker, testtime = instr.get_VSA_sweep_noise_mkr()
        self.assertIsInstance(marker, float)
        self.assertIsInstance(testtime, (float, int))
if __name__ == '__main__':
    unittest.main()
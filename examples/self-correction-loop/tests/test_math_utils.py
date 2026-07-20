import unittest

from math_utils import calculate_sum


class TestMathUtils(unittest.TestCase):
    def test_calculate_sum(self):
        self.assertEqual(calculate_sum([1, 2, 3]), 6)

if __name__ == "__main__":
    unittest.main()

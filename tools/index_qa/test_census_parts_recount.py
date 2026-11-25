import unittest
import census_parts_recount as M


class T(unittest.TestCase):
    def test_line_matches_serial_format(self):
        rep = {'sample': {'severe': (67, 1624, (0.041, 0.020, 0.060))}}
        self.assertEqual(M.severe_line(rep), '📐 العطب الجسيم (إسقاط كلمة): 67/1624 = 4.1% · مجال 95% عنقودي: 2.0% – 6.0%')

    def test_empty(self):
        self.assertTrue(M.severe_line({'sample': {'severe': (0, 0, None)}}).endswith('—'))


if __name__ == '__main__':
    unittest.main()

"""
Simple unittest battery that checks
  1) The CAT-62 XML loads.
  2) A trivial (empty-payload) packet decodes and returns an empty dict.

Run   python -m unittest test_decoder.py
"""
import unittest
from pathlib import Path

from src.spec import Cat62Spec
from src.decoder import AsterixDecoder


XML_PATH = Path(__file__).with_name("asterix_cat062_1_17.xml")


class Cat62SpecTests(unittest.TestCase):
    def test_loads_and_contains_key_items(self):
        spec = Cat62Spec(XML_PATH)
        self.assertIn("010", spec)                  # Data Source Identifier
        self.assertGreater(len(spec.uap), 0)


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.spec = Cat62Spec(XML_PATH)

    def test_empty_packet(self):
        # Category 62, length = 4, FSPEC octet = 0x00  -> no items
        raw = bytes([62, 0, 4, 0x00])
        dec = AsterixDecoder(raw, self.spec)
        record = dec.decode()
        self.assertEqual(record, {})


if __name__ == "__main__":
    unittest.main()

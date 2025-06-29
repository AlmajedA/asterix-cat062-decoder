import logging
from pathlib import Path

from src.spec import Cat62Spec
from src.decoder import Cat62Decoder

logging.basicConfig(level=logging.INFO)

def main():
    spec = Cat62Spec("xmls/asterix_cat062_1_17.xml")
    raw  = bytes.fromhex(Path("data2.txt").read_text())
    decoder = Cat62Decoder(raw)
    records = decoder.decode()
    decoder.pretty(records)
    

if __name__ == "__main__":
    main()

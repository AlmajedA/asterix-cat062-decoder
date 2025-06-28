import logging
from pathlib import Path

from src.spec import Cat62Spec
from src.decoder import Cat62Decoder

logging.basicConfig(level=logging.INFO)

def main() -> None:
    spec = Cat62Spec("xmls/asterix_cat062_1_17.xml")
    raw  = bytes.fromhex(Path("data.txt").read_text())
    decoder = Cat62Decoder(raw, spec)
    records = decoder.decode()
    decoder.pprint_records(records, show_raw_hex=True)

    print(records)
    

if __name__ == "__main__":
    main()

import logging
from pathlib import Path

from src.spec import Cat62Spec
from src.decoder_backup import Cat62Decoder

logging.basicConfig(level=logging.INFO)

def main() -> None:
    spec = Cat62Spec("xmls/asterix_cat062_1_17.xml")
    raw  = bytes.fromhex(Path("data.txt").read_text())
    decoder = Cat62Decoder(raw)
    records = decoder.decode()
    print(records)

    # decoder.pretty(records)
    # print(records)
    

if __name__ == "__main__":
    main()

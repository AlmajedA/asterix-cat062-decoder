from struct import unpack_from
from typing import Dict, Any, List

with open('data.txt', 'r') as file:
        data = file.read()
data = bytes.fromhex(data)

class Cat62Decoder:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.p = 0          # read pointer

    def _read(self, n):
        chunk = self.raw[self.p:self.p+n]
        self.p += n
        return chunk
    
    def decode(self):
        cat = self._read(1)[0]
        if cat != 62:
            raise ValueError("Not CAT-62")
        length = int.from_bytes(self._read(2), "big")
        assert length == len(self.raw), "length field mismatch"
        print(length)
        # we’ll fill the rest later

Cat62Decoder(data).decode()
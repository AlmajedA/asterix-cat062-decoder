from struct import unpack_from
from typing import Dict, Any, List
from src.spec import Cat62Spec

with open('data.txt', 'r') as file:
        data = file.read()
        
data = bytes.fromhex(data)

xml_path = "xmls/asterix_cat062_1_17.xml"
class Cat62Decoder:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.p = 0          # read pointer
        self.SPEC = Cat62Spec(xml_path)

    def _read(self, n):
        chunk = self.raw[self.p:self.p+n]
        self.p += n
        return chunk
    
    def _get_length(self, length_data):
         return int.from_bytes(length_data, "big")
    
    def decode(self):
        cat = self._read(1)[0]
        if cat != 62:
            raise ValueError("Not CAT-62")
        length = self._get_length(self._read(2))
        assert length == len(self.raw), "length field mismatch"
        fspec_octets = []
        while True:
            oc = self._read(1)[0]
            fspec_octets.append(oc)
            if oc & 1 == 0:      # FX == 0
                break

        bit_index = 0
        present_ids = []
        for oc in fspec_octets:
            for bit in range(7):                    # bits 8..2
                if oc & (1 << (7 - bit)):    
                    present_ids.append(self.SPEC.uap[bit_index])
                bit_index += 1
            bit_index += 1                        # skip FX


        for id in present_ids:
            meta = self.SPEC.items[id]
            t = meta["type"]
            if t == "Fixed":
                value = self._decode_fixed(meta)        # unchanged
            elif t == "Variable":
                pass
                # value = self._decode_variable(meta)
            elif t == "Repetitive":
                pass
                # value = self._decode_repetitive(meta)
            elif t == "Compound":
                pass
                # value = self._decode_compound(meta)
            else:
                raise NotImplementedError(t)
            # break


    def _decode_fixed(self, spec):
        spec_length = int(spec['length'])
        raw = self._read(spec_length)
        val = int.from_bytes(raw, "big")
        total = spec_length * 8
        out = {}
        bits = spec['bits']
        for bit in bits:

            bit_start = int(bit['start'])
            bit_end = int(bit['end'])
            width = bit_start - bit_end + 1
            shift  = bit_end - 1
            field = (val >> shift) & ((1 << width) - 1)
            
            # if bit["signed"]:
            #     sign = 1 << (width-1)
            #     if field & sign:
            #         field -= 1 << width
            # elif bit["octal"]:
            #     pass
            # elif bit["sixchar"]:
            #     pass
            out[bit["name"]] = field
        print(out)
        return out

Cat62Decoder(data).decode()
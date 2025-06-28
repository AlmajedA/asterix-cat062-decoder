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
        print(present_ids)
        result = {}

        for id in present_ids:
            meta = self.SPEC.items[id]
            t = meta["type"]
            if t == "Fixed":
                fixed_output = self._decode_fixed(meta)
                result[id] = fixed_output

            elif t == "Variable":
                variable_output = self._decode_variable(meta)
                result[id] = variable_output
            elif t == "Compound":
            
                compound_output = self._decode_compound(meta)
                result[id] = compound_output
            else:
                raise NotImplementedError(t)
            
            
            
        print(result)
        print(self.p)
        print(length)

    def _decode_fixed(self, spec):
        spec_length = int(spec['length'])
        raw = self._read(spec_length)
        val = int.from_bytes(raw, "big")
        out = {}
        bits = spec['bits']
        for bit in bits:

            bit_start = int(bit['start'])
            bit_end = int(bit['end'])
            width = bit_start - bit_end + 1
            shift  = bit_end - 1
            field = (val >> shift) & ((1 << width) - 1)
            
            # if bit["signed"]:
            #     field = self._twos_complement(field, width)

            # elif bit["octal"]:
            #     field = self._octal_code(field, width)      # returns e.g. "0421"

            # elif bit["sixchar"]:
            #     field = self._ia5_6bit_string(field, width) # returns e.g. "AFR123 "

            # if bit["scale"]:
            #     field *= bit["scale"]
            out[bit["name"]] = field
        return out
    
    # def _decode_variable(self, spec):
    #     out = []
    #     for f in spec["inners"]:
    #         fixed_output = self._decode_fixed(f)
    #         out.append(fixed_output)
    #         if fixed_output['FX'] == 0:
    #             break

    #     return out
    def _decode_variable(self, spec, *, need_presence=False):
        """Return a list of decoded octets plus, optionally, a list of 1/0
        presence flags that correspond to bits 8…2, 8…2, …  (FX omitted)."""
        octets_out: List[Dict[str, Any]] = []
        presence:   List[bool]           = []

        for inner in spec["inners"]:
            # decode this 1-octet <Fixed> header --------------------------
            octet = self._decode_fixed(inner)
            octets_out.append(octet)

            # build the presence mask (bit-order is already 8→1 in XML)
            if need_presence:
                for meta in inner["bits"]:
                    if meta["name"] != "FX":                 # skip the extension bit
                        presence.append(octet[meta["name"]] == 1)

            # stop if FX == 0
            if octet["FX"] == 0:
                break

        return (octets_out, presence) if need_presence else octets_out
    def _decode_repetitive(self, spec):
        rep_time = self._read(1)[0]
        print(rep_time)
        out = []
        inner_spec = spec["inners"][0]
        for i in range(rep_time):
            fixed_output = self._decode_fixed(inner_spec)
            out.append(fixed_output)
        return out

    
    def _decode_compound(self, spec):
        subs = spec["subs"]      # [Variable-hdr, sub-1, sub-2, …]
        out  = {}

        # ── step 1 · decode the primary variable header ─────────────────
        var_meta     = subs[0]
        var_decoded, presence = self._decode_variable(var_meta, need_presence=True)
        out["HDR"]   = var_decoded     # keep the header itself

        # ── step 2 · walk through the rest, guided by ‘presence’ flags ──
        sub_idx = 1        # current entry in subs[1:]
        for present in presence:
            if sub_idx >= len(subs):           # XML spare bits possible
                break

            if present:                        # only when bit == 1
                sub_spec = subs[sub_idx]
                t        = sub_spec["type"]

                if   t == "Fixed":
                    out[sub_idx] = self._decode_fixed(sub_spec)
                elif t == "Variable":
                    out[sub_idx] = self._decode_variable(sub_spec)
                elif t == "Repetitive":
                    out[sub_idx] = self._decode_repetitive(sub_spec)
                else:
                    raise NotImplementedError(t)

            sub_idx += 1                       # advance to next sub-field

        return out
    


Cat62Decoder(data).decode()
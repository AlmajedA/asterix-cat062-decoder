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
        final_result = []

        while self.p != length:
            result = {}
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
            
            final_result.append(result)

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
    
    def _decode_variable(self, spec, *, need_presence=False):
        """
        Decode a <Variable> item that may have 1..N extents.
        Works for both:
        • presence-vector variables with several different 1-byte templates
        • repeat-the-same-template variables (e.g. I062/510, 3-byte blocks)
        """
        inners = spec["inners"]
        n_tmpl = len(inners)

        octets_out: list[dict] = []
        presence  : list[bool] = []

        idx = 0                       # which inner template to use next
        while True:
            inner_meta = inners[idx]
            octet = self._decode_fixed(inner_meta)
            octets_out.append(octet)

            # build presence vector if requested
            if need_presence:
                for meta in inner_meta["bits"]:
                    if meta["name"] != "FX":
                        presence.append(octet[meta["name"]] == 1)

            # stop condition
            if octet["FX"] == 0:
                break

            # choose template for the *next* extent -----------------------
            if n_tmpl == 1:           # only one template → repeat it
                idx = 0
            else:                     # multi-template presence vector
                idx += 1
                if idx >= n_tmpl:
                    raise ValueError("FX=1 but no further <Fixed> template in XML")

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
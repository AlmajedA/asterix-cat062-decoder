from struct import unpack_from
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

        records = []

        while self.p != length:
            record = {}
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
                    fixed_output = self._decode_fixed(meta)
                    record[id] = fixed_output

                elif t == "Variable":
                    variable_output = self._decode_variable(meta)
                    record[id] = variable_output
                elif t == "Compound":
                
                    compound_output = self._decode_compound(meta)
                    record[id] = compound_output


            
            records.append(record)
        return records
        
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
            x = (val >> shift) & ((1 << width) - 1)
            
            if bit["signed"]:
                sign = 1 << (width - 1)
                if x & sign:
                    x -= 1 << width
            elif bit["octal"]:
                x = format(x, f"0{width//3}o")
            elif bit["sixchar"]:
                chars = [chr(((x >> (6*i)) & 0x3F) + 0x20)
                         for i in range((width // 6) - 1, -1, -1)]
                x = "".join(chars).rstrip()

            if bit["scale"]:
                x *= bit["scale"]

            out[bit["name"]] = x
        return out
    
    def _decode_variable(self, spec, *, need_presence=False):
        inners = spec["inners"]
        n_tmpl = len(inners)

        octets_out = []
        presence = []

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

        return (octets_out, presence) if need_presence else octets_out
    
    def _decode_repetitive(self, spec):
        rep_time = self._read(1)[0]
        out = []
        inner_spec = spec["inners"][0]
        for i in range(rep_time):
            fixed_output = self._decode_fixed(inner_spec)
            out.append(fixed_output)
        return out

    
        # ───────────────────────── Compound format ──────────────────────────
    def _decode_compound(self, spec):
        """
        Decode a Compound data-item.

        * Header (variable presence vector) is stored under key "HDR".
        * Each present sub-item is stored under the short-name of the header
          bit that announced it, rather than a numeric position.
        """
        subs = spec["subs"]             # [Variable-HDR, sub-1, sub-2, …]

        # -------- 1. decode the presence vector ------------------------
        hdr_meta        = subs[0]                       # Variable
        hdr_exts, flags = self._decode_variable(hdr_meta, need_presence=True)
        out             = {"HDR": hdr_exts}

        # Build the list of header-bit names in the same order as *flags*
        bit_names = []
        for inner in hdr_meta["inners"]:
            for b in inner["bits"]:
                if b["name"] != "FX":
                    bit_names.append(b["name"])

        # -------- 2. walk through the remaining sub-fields -------------
        for idx, (present, bit_name) in enumerate(zip(flags, bit_names), start=1):
            if idx >= len(subs):        # spare bits beyond defined subs
                break
            if not present:
                continue

            sub_meta = subs[idx]
            t        = sub_meta["type"]

            if   t == "Fixed":
                out[bit_name] = self._decode_fixed(sub_meta)
            elif t == "Variable":
                out[bit_name] = self._decode_variable(sub_meta)
            elif t == "Repetitive":
                out[bit_name] = self._decode_repetitive(sub_meta)

        return out

    
    def pprint(self, records):
        for record in records:
            for reference_number, data_item in record.items():
                print(self.SPEC.items[reference_number])
                print(reference_number, data_item)
    
    # ─────────────────────────── pretty tree ────────────────────────────
    def pretty(self, records, indent=2):
        """Print decoded records using full Data-Item & Bit names."""

        pad = lambda lvl: " " * (lvl * indent)

        def title(item_id, meta):
            return f"[{item_id}] {meta.get('full_name','')}"

        # -------- Fixed -------------------------------------------------
        def show_fixed(item_id, meta, val, lvl):
            print(f"{pad(lvl)}{title(item_id, meta)}")
            for bit in meta["bits"]:
                n_short = bit["name"]
                n_full  = bit["full_name"]
                v       = val.get(n_short)
                print(f"{pad(lvl+1)}• {n_full}: {v}")

        # -------- Variable ---------------------------------------------
        def show_variable(item_id, meta, val, lvl):
            print(f"{pad(lvl)}{title(item_id, meta)}")
            inner = meta["inners"][0]
            for i, ext in enumerate(val):
                print(f"{pad(lvl+1)}extent {i}:")
                show_fixed(f"{item_id}.{i}", inner, ext, lvl+2)

        # -------- Repetitive -------------------------------------------
        def show_repetitive(item_id, meta, val, lvl):
            print(f"{pad(lvl)}{title(item_id, meta)}")
            inner = meta["inners"][0]
            for i, rep in enumerate(val):
                show_fixed(f"{item_id}.{i}", inner, rep, lvl+1)

                # -------- Compound ---------------------------------------------
        def show_compound(item_id, meta, val, lvl):
            print(f"{pad(lvl)}{title(item_id, meta)}")

            subs = meta["subs"]          # [Variable-HDR, sub-1, sub-2, …]

            # ── 1) header vector (always first sub when present) ───────
            hdr_present = subs and subs[0]["type"] == "Variable"
            it = iter(subs)

            if hdr_present:
                hdr_meta = next(it)
                show_variable(f"{item_id}.HDR", hdr_meta, val["HDR"], lvl+1)

                # Build the *short names* in header-bit order
                bit_names = []
                for inner in hdr_meta["inners"]:
                    for b in inner["bits"]:
                        if b["name"] != "FX":
                            bit_names.append(b["name"])
                names_iter = iter(bit_names)
            else:
                names_iter = iter([])    # no header → no presence vector

            # ── 2) remaining sub-fields, keyed by short name ───────────
            for sub_meta in it:
                try:
                    key = next(names_iter)
                except StopIteration:
                    key = "?"            # spare / undefined bits

                if key in val:           # only show if actually present
                    show_any(f"{item_id}.{key}", sub_meta, val[key], lvl+1)

        # -------- dispatcher -------------------------------------------
        def show_any(item_id, meta, val, lvl):
            t = meta["type"]
            if t == "Fixed":
                show_fixed(item_id, meta, val, lvl)
            elif t == "Variable":
                show_variable(item_id, meta, val, lvl)
            elif t == "Repetitive":
                show_repetitive(item_id, meta, val, lvl)
            elif t == "Compound":
                show_compound(item_id, meta, val, lvl)

        # -------- walk every record ------------------------------------
        for r, rec in enumerate(records, 1):
            print(f"Record #{r}")
            for item_id, item_val in rec.items():
                show_any(item_id, self.SPEC.items[item_id], item_val, 1)
            print()





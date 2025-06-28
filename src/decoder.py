from __future__ import annotations

import logging
from struct import unpack_from
from typing import Any, Dict, List, Union, Tuple

from src.spec import Cat62Spec

logger = logging.getLogger(__name__)


class Cat62Decoder:
    """Decode one **byte string** that may contain *several* CAT-62 records."""

    # --------------------------------------------------------------------- init
    def __init__(self, raw: bytes, spec: Cat62Spec) -> None:
        self._raw = raw
        self._pos = 0                       # cursor into self._raw
        self._spec = spec

    # ----------------------------------------------------------------- helpers
    def _read(self, n: int) -> bytes:
        """Return *n* bytes and advance cursor."""
        if self._pos + n > len(self._raw):
            raise ValueError("unexpected end-of-buffer")
        chunk = self._raw[self._pos : self._pos + n]
        self._pos += n
        return chunk

    def _read_u8(self) -> int:
        val, = unpack_from(">B", self._raw, self._pos)
        self._pos += 1
        return val

    def _read_u16(self) -> int:
        val, = unpack_from(">H", self._raw, self._pos)
        self._pos += 2
        return val

    # ------------------------------------------------------------------ public
    def decode(self) -> List[Dict[str, Any]]:
        """Decode *all* CAT-62 packets contained in *raw*."""
        records: List[Dict[str, Any]] = []

        while self._pos < len(self._raw):
            records.append(self._decode_one_record())

        return records

    # ------------------------------------------------------------------ record
    def _decode_one_record(self) -> Dict[str, Any]:
        """Decode exactly one CAT-62 record and return a dict of data items."""
        category = self._read_u8()
        if category != 62:
            raise ValueError(f"expected CAT-62, got CAT-{category}")

        length   = self._read_u16()
        record_end = self._pos + length - 3   # 3 bytes already consumed

        fspec_octets = self._read_fspec()
        item_ids     = self._map_fspec_to_items(fspec_octets)

        record: Dict[str, Any] = {}
        for item_id in item_ids:
            meta = self._spec.items[item_id]
            record[item_id] = self._decode_item(meta)

        # ensure we consumed exactly this record
        if self._pos != record_end:
            # skip any spare bytes to stay in sync but log a warning
            logger.warning("cursor mis-aligned: skipping %d spare bytes",
                           record_end - self._pos)
            self._pos = record_end

        return record

    # ----------------------------------------------------------- FSPEC helpers
    def _read_fspec(self) -> List[int]:
        """Return a list of FSPEC octets (integers)."""
        octets: List[int] = []
        while True:
            oc = self._read_u8()
            octets.append(oc)
            if oc & 0x01 == 0:          # FX bit cleared → last octet
                break
        return octets

    def _map_fspec_to_items(self, fspec_octets: List[int]) -> List[str]:
        """Translate FSPEC bitmap to a list of Data-Item IDs (strings)."""
        present: List[str] = []
        bit_index = 0                   # current UAP position

        for oc in fspec_octets:
            for local in range(7):      # bits 8…2
                if oc & (1 << (7 - local)):
                    present.append(self._spec.uap[bit_index])
                bit_index += 1
            bit_index += 1              # skip FX slot

        return present

    # ----------------------------------------------------------- item decoder
    def _decode_item(self, meta: Dict[str, Any]) -> Any:
        dispatch = {
            "Fixed"      : self._decode_fixed,
            "Variable"   : self._decode_variable,
            "Compound"   : self._decode_compound,
        }
        try:
            return dispatch[meta["type"]](meta)  # type: ignore[arg-type]
        except KeyError:
            raise NotImplementedError(meta["type"])

    # ------------------------------------------------ Fixed (single template)
    def _decode_fixed(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Decode a Fixed-length item according to *meta*."""
        raw   = self._read(meta["length"])
        value = int.from_bytes(raw, "big")

        result: Dict[str, Any] = {}
        for field in meta["bits"]:
            start, end = field["start"], field["end"]
            width      = start - end + 1
            shift      = end - 1
            mask       = (1 << width) - 1
            x          = (value >> shift) & mask

            # post-processing
            if field["signed"]:
                sign = 1 << (width - 1)
                if x & sign:
                    x -= 1 << width
            elif field["octal"]:
                digits = width // 3
                x = format(x, f"0{digits}o")
            elif field["sixchar"]:
                chars = [chr(((x >> (6*i)) & 0x3F) + 0x20)
                         for i in range((width // 6) - 1, -1, -1)]
                x = "".join(chars).rstrip()

            if field["scale"]:
                x *= field["scale"]

            result[field["name"]] = x
        return result

    # ------------------------------------------------ Variable (1…N extents)
    def _decode_variable(
        self,
        meta: Dict[str, Any],
        *,                        # force keyword
        need_presence: bool = False
    ) -> Union[
            List[Dict[str, Any]],              # default return
            Tuple[List[Dict[str, Any]],        # when need_presence=True
                List[bool]]
        ]:
        """
        Decode a <Variable> item that may consist of 1‥N extents.

        Parameters
        ----------
        meta : mapping produced by spec.py
            Must contain key ``"inners"`` – a list of Fixed-template dicts.
        need_presence : bool, default False
            If True, also returns a flat list of booleans that correspond to
            bits 8…2, 8…2, … of the templates (FX bits omitted).  This is used
            by compound items to decide which sub-fields follow.

        Returns
        -------
        list[dict]
            One decoded dict per extent, **or**
        (list[dict], list[bool])
            If *need_presence* was True.
        """
        inners = meta["inners"]
        n_tpl  = len(inners)

        extents:   List[Dict[str, Any]] = []
        presence:  List[bool]           = []

        idx = 0                                 # template index
        while True:
            tmpl   = inners[idx]
            extent = self._decode_fixed(tmpl)
            extents.append(extent)

            if need_presence:
                for field in tmpl["bits"]:
                    if field["name"] != "FX":    # ignore extension flag
                        presence.append(extent[field["name"]] == 1)

            # ── done?  FX == 0  → stop
            if extent["FX"] == 0:
                break

            # ── choose next template
            idx = 0 if n_tpl == 1 else idx + 1
            if idx >= n_tpl:
                raise ValueError(
                    "FX=1 but no further <Fixed> template defined in XML"
                )

        return (extents, presence) if need_presence else extents

    # ------------------------------------------------ Compound (indicator map)
    def _decode_compound(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Decode a Compound item (indicator bitmap + sub-fields)."""
        indicator_ext, present_flags = self._decode_variable(
            meta["subs"][0], need_presence=True
        )

        out: Dict[str, Any] = {"HDR": indicator_ext}
        subs_iter = iter(meta["subs"][1:])
        for flag in present_flags:
            try:
                sub_meta = next(subs_iter)
            except StopIteration:
                break
            if flag:
                out[sub_meta.get("id", len(out))] = self._decode_item(sub_meta)
        return out
    
    # ------------------------------------------------------------------ pretty-printer
    def pprint_records(
        self,
        records: List[Dict[str, Any]],
        *,
        show_raw_hex: bool = False,
        indent: int = 2,
    ) -> None:
        """
        Nicely print CAT-62 records to stdout.

        Parameters
        ----------
        records : list[dict]
            The list produced by ``Cat62Decoder.decode()``.
        show_raw_hex : bool, default False
            If True, prints one “record: len=… hex=…” line (like in your
            example) before each record tree.
        indent : int, default 2
            Number of spaces per indentation level.
        """

        def _indent(level: int) -> str:
            return " " * (indent * level)

        def _fmt_hex(byte_seq: bytes) -> str:
            return byte_seq.hex()

        def _fmt_bin(value: int, width: int) -> str:
            bits = format(value, f"0{width}b")
            # group as “xxxx xxxx …”
            return " ".join(bits[i : i + 8] for i in range(0, width, 8))

        def _print_field(path: List[str], meta: Dict[str, Any], val: Any, lvl: int) -> None:
            """Recursive helper for Fixed / Variable / Repetitive structures."""
            name_path = "', '".join(path)
            print(f"{_indent(lvl)}['{name_path}']: \"{meta.get('desc', '')}\"")

            if meta["type"] == "Fixed":
                width = meta["length"] * 8
                raw_int = val["__raw__"] if isinstance(val, dict) and "__raw__" in val else None
                if raw_int is not None:
                    print(f"{_indent(lvl+1)}len={width} bits, bin={_fmt_bin(raw_int, width)}")

                for bit_meta in meta["bits"]:
                    fld_name = bit_meta["name"]
                    field_val = val.get(fld_name)
                    _print_field(path + [fld_name], bit_meta, field_val, lvl + 2)

            elif meta["type"] == "Variable":
                for idx, extent in enumerate(val):
                    print(f"{_indent(lvl+1)}extent {idx}:")
                    for f_meta in meta["inners"][0]["bits"]:
                        _print_field(path + [f"({idx})"], f_meta, extent[f_meta["name"]], lvl + 2)

            elif meta["type"] == "Repetitive":
                for idx, rep in enumerate(val):
                    print(f"{_indent(lvl+1)}subitem ({idx})")
                    inner_meta = meta["inners"][0]
                    for f_meta in inner_meta["bits"]:
                        _print_field(path + [f"({idx})"], f_meta, rep[f_meta["name"]], lvl + 2)
            elif meta["type"] == "Compound":
                # header
                hdr_meta = meta["subs"][0]
                _print_field(path + ["HDR"], hdr_meta, val["HDR"], lvl + 1)
                # sub-fields
                for idx, sub_meta in enumerate(meta["subs"][1:], start=1):
                    if idx in val:  # present
                        _print_field(path + [str(idx)], sub_meta, val[idx], lvl + 1)

            else:  # leaf value
                if isinstance(val, (int, float, str)):
                    print(f"{_indent(lvl+1)}Element: value: {val}")
                else:
                    print(f"{_indent(lvl+1)}{val}")

        # ------------- main loop over records --------------------------
        for rec_idx, record in enumerate(records):
            raw_slice = b""  # placeholder – fill if you kept raw bytes per record
            if show_raw_hex:
                print(
                    f"record #{rec_idx}: len={len(raw_slice)} bytes, "
                    f"hex={_fmt_hex(raw_slice)}"
                )

            for item_id, item_val in record.items():
                meta = self._spec.items[item_id]
                _print_field([item_id], meta, item_val, lvl=0)

            print()  # blank line between records


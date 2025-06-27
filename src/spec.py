# spec.py ─────────────────────────────────────────────────────────────
import xml.etree.ElementTree as ET

# ── helper #1 : turn one <Fixed> into meta-dict ──────────────────────
def _fixed_meta(fx: ET.Element) -> dict:
    return {
        "type":  "Fixed",
        "length": int(fx.attrib["length"]),
        "bits":  _extract_bits(fx),
    }

# ── helper #2 : extract every <Bits> field inside one <Fixed> ───────
def _extract_bits(fx: ET.Element) -> list[dict]:
    out = []
    for b in fx.findall(".//Bits"):
        # locate the bit range
        if "bit" in b.attrib:                # single bit
            start = end = int(b.attrib["bit"])
        else:                                # range
            start = int(b.attrib["from"])
            end   = int(b.attrib["to"])
        if start < end:                      # normalise to start ≥ end
            start, end = end, start

        out.append({
            "name"   : b.findtext("BitsShortName")
                       or b.findtext("BitsName")
                       or f"bit{start}",
            "start"  : start,
            "end"    : end,
            "signed" : b.attrib.get("encode") == "signed",
            "octal"  : b.attrib.get("encode") == "octal",
            "sixchar": b.attrib.get("encode") == "6bitschar",
            "scale"  : (
                float(b.find("BitsUnit").attrib["scale"])
                if b.find("BitsUnit") is not None else None
            ),
        })
    return out

# ── helper #3 : create meta for Fixed / Variable / Repetitive ───────
def _format_meta(node: ET.Element) -> dict:
    tag = node.tag
    if tag == "Fixed":
        return _fixed_meta(node)

    if tag in ("Variable", "Repetitive"):
        inners = [_fixed_meta(fx) for fx in node.findall("Fixed")]
        return {"type": tag, "inners": inners}

    raise ValueError(f"Unexpected tag <{tag}> inside Compound")

# ── main Cat62Spec class ─────────────────────────────────────────────
class Cat62Spec:
    """Parse CAT-62 XML (inline compound children, no <DataItemRef>)."""

    def __init__(self, xml_path: str) -> None:
        root = ET.parse(xml_path).getroot()

        # --- UAP: needed for FSPEC → ID mapping ----------------------
        self.uap = [
            e.text.strip()
            for e in root.find("UAP").findall("UAPItem")
        ]

        self.items: dict[str, dict] = {}

        # --- walk every <DataItem> -----------------------------------
        for di in root.findall("DataItem"):
            did      = di.attrib["id"]
            fmt_node = di.find("DataItemFormat")[0]   # first child
            tag      = fmt_node.tag

            meta: dict = {"type": tag}

            if tag == "Fixed":
                meta.update(_fixed_meta(fmt_node))

            elif tag in ("Variable", "Repetitive"):
                meta["inners"] = [_fixed_meta(fx)
                                 for fx in fmt_node.findall("Fixed")]

            elif tag == "Compound":
                subs = []
                for child in fmt_node:
                    if child.tag == "Indicator":      # bitmap description → skip
                        continue
                    subs.append(_format_meta(child))  # Fixed / Variable / Repetitive
                meta["subs"] = subs

            self.items[did] = meta

    # convenience getter
    def get_data_items(self):
        return self.items

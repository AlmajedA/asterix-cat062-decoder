import xml.etree.ElementTree as ET

def _extract_bits(fx):
    """Return list of dicts for each <Bits> element under one <Fixed> node."""
    bits = []
    for b in fx.findall(".//Bits"):

        if "bit" in b.attrib:
            start = end = int(b.attrib["bit"])
        else:
            start, end = int(b.attrib["from"]), int(b.attrib["to"])
            if start < end:
                start, end = end, start            # normalise

        short = b.findtext("BitsShortName") or b.findtext("BitsName") or f"bit{start}"
        full  = b.findtext("BitsName")            # can be None
        full  = full.strip() if full else short   # ensure a string

        bits.append({
            "name"      : short,                  # short key used in decoded dict
            "full_name" : full,                   # ← NEW
            "start"     : start,
            "end"       : end,
            "signed"    : b.attrib.get("encode") == "signed",
            "octal"     : b.attrib.get("encode") == "octal",
            "sixchar"   : b.attrib.get("encode") == "6bitschar",
            "scale"     : (
                float(b.find("BitsUnit").attrib["scale"])
                if b.find("BitsUnit") is not None else None
            ),
        })
    return bits


def _fixed_meta(fx):
    return {
        "type"      : "Fixed",
        "length"    : int(fx.attrib["length"]),
        "bits"      : _extract_bits(fx),
    }


def _format_meta(node):
    tag = node.tag
    if tag == "Fixed":
        return _fixed_meta(node)
    if tag in ("Variable", "Repetitive"):
        return {"type": tag, "inners": [_fixed_meta(fx) for fx in node.findall("Fixed")]}
    raise ValueError(f"Unexpected tag <{tag}> inside Compound")


class Cat62Spec:
    """Parse CAT-62 XML (inline compound children; no <DataItemRef>)."""

    def __init__(self, xml_path):
        root = ET.parse(xml_path).getroot()

        # UAP (FSPEC ↔ Data-Item ID)
        self.uap = [e.text.strip() for e in root.find("UAP").findall("UAPItem")]

        self.items = {}

        for di in root.findall("DataItem"):
            did       = di.attrib["id"]
            full_name = di.findtext("DataItemName", "").strip()
            fmt_node  = di.find("DataItemFormat")[0]
            tag       = fmt_node.tag

            meta = {"type": tag, "full_name": full_name}

            if tag == "Fixed":
                meta.update(_fixed_meta(fmt_node))

            elif tag in ("Variable", "Repetitive"):
                meta["inners"] = [_fixed_meta(fx) for fx in fmt_node.findall("Fixed")]

            elif tag == "Compound":
                subs = []
                for child in fmt_node:
                    if child.tag == "Indicator":
                        continue
                    subs.append(_format_meta(child))
                meta["subs"] = subs

            self.items[did] = meta

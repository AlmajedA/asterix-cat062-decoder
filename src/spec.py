import xml.etree.ElementTree as ET
from pathlib import Path

def _extract_bits(fixed_node):
    """
    Return a list of dicts, one for every <Bits …> element that lives
    *anywhere* under the given <Fixed> node.
    """
    bits = []
    for b in fixed_node.findall(".//Bits"):
        # single bit ⇒ attribute “bit”
        if "bit" in b.attrib:               # e.g. <Bits bit="16">
            start = end = int(b.attrib["bit"])
        else:                               # bit range ⇒ “from … to …”
            start = int(b.attrib["from"])
            end   = int(b.attrib["to"])
        
        if start < end:                      
            start, end = end, start

        bits.append(
            {
                "name": (
                    b.findtext("BitsShortName")
                    or b.findtext("BitsName")
                    or f"{start}"
                ),
                "start": start,
                "end":   end,
                "signed":  b.attrib.get("encode") == "signed",
                "octal":   b.attrib.get("encode") == "octal",
                "sixchar": b.attrib.get("encode") == "6bitschar",
                "scale": (
                    float(b.find("BitsUnit").attrib["scale"])
                    if b.find("BitsUnit") is not None
                    else None
                ),
            }
        )
    return bits

def _fixed_meta(fixed_xml):
    """Return {'length': int, 'bits': list[…]} for ONE <Fixed>."""
    return {
        "length": int(fixed_xml.attrib["length"]),
        "bits":   _extract_bits(fixed_xml),
    }


class Cat62Spec:
    def __init__(self, xml_path):
        root = ET.parse(xml_path).getroot()
        self.uap = [e.text.strip()
                    for e in root.find("UAP").findall("UAPItem")
                    ]

        self.items = {}
        for di in root.findall("DataItem"):
            id_ = di.attrib["id"]
            fmt_node = di.find("DataItemFormat")[0]
            fmt_type = fmt_node.tag

            entry = {"type": fmt_type, "xml": di, "fmt": fmt_node}

            if fmt_type == "Fixed":
                entry["length"] = int(fmt_node.attrib["length"])
                entry["bits"]   = _extract_bits(fmt_node)

            elif fmt_type == "Variable":
                inner_fixes = [_fixed_meta(fx) for fx in fmt_node.findall("Fixed")]
                entry["inners"] = inner_fixes          # now a list of 1…N dicts

            elif fmt_type == "Repetitive":
                inner_fixes = [_fixed_meta(fx) for fx in fmt_node.findall("Fixed")]
                entry["inners"] = inner_fixes          # same structure

            elif fmt_type == "Compound":
                entry["sub_ids"] = [
                    ref.attrib["id"] for ref in fmt_node.findall("DataItemRef")
                ]

            self.items[id_] = entry

    def get_data_items(self):
        return self.items
# import xml.etree.ElementTree as ET
# root = ET.parse("./xmls/asterix_cat062_1_17.xml").getroot()
# print(root.tag, root.attrib)
# uap = [e.text.strip() for e in root.find("UAP").findall("UAPItem") if e.text.strip() != "-"]
# print(uap)
# di = root.find(".//DataItem[@id='010']")
# print(di.find("DataItemName").text)
# fmt = di.find("DataItemFormat")[0]
# print(fmt.tag, fmt.attrib)

import xml.etree.ElementTree as ET

class XMLParser:
    def parse(self, xml_content: str):
        return ET.fromstring(xml_content)

    def to_string(self, root) -> str:
        return ET.tostring(root, encoding="unicode")

    def load_xsd(self, xsd_content: str) -> dict:
        try:
            ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
            return {el.get("name"): el.get("type","").replace("xs:","")
                    for el in ET.fromstring(xsd_content).findall(".//xs:element", ns)
                    if el.get("name") and el.get("type")}
        except Exception as e:
            print(f"[XMLParser] XSD error: {e}"); return {}

    def get_datatype(self, param_name, rules, value=""):
        tag = param_name.split(".")[-1]
        if tag in rules: return rules[tag]
        v = str(value).strip()
        if v.lower() in ("true","false","1","0"): return "boolean"
        try: int(v); return "integer"
        except ValueError: pass
        try: float(v); return "float"
        except ValueError: pass
        return "string"

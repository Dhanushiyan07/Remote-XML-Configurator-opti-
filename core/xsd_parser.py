import xml.etree.ElementTree as ET

class XSDParser:
    NS = {"xs": "http://www.w3.org/2001/XMLSchema"}

    def load_types(self, xsd_content: str) -> dict:
        try: root = ET.fromstring(xsd_content)
        except ET.ParseError as e:
            print(f"[XSDParser] Error: {e}"); return {}
        ns = self.NS

        # named simpleTypes (enum, range, pattern)
        simple_types = {}
        for st in root.findall(".//xs:simpleType", ns):
            name = st.get("name")
            if name:
                rule = self._restriction(st.find("xs:restriction", ns), ns)
                if rule: simple_types[name] = rule

        out = {}
        for el in root.findall(".//xs:element", ns):
            name = el.get("name")
            if not name: continue
            rule = {}
            dtype = el.get("type")
            if dtype:
                clean = dtype.replace("xs:","")
                rule["type"] = clean
                if clean in simple_types: rule.update(simple_types[clean])
            restr = el.find(".//xs:restriction", ns)
            if restr is not None: rule.update(self._restriction(restr, ns))
            if el.get("default") is not None: rule["default"] = el.get("default")
            if el.get("fixed") is not None:   rule["fixed"] = el.get("fixed")
            rule["required"] = el.get("minOccurs","1") != "0"
            if el.get("maxOccurs"): rule["maxOccurs"] = el.get("maxOccurs")
            if rule: out[name] = rule

        for attr in root.findall(".//xs:attribute", ns):
            name = attr.get("name")
            if not name: continue
            rule = {}
            atype = attr.get("type")
            if atype:
                clean = atype.replace("xs:","")
                rule["type"] = clean
                if clean in simple_types: rule.update(simple_types[clean])
            restr = attr.find(".//xs:restriction", ns)
            if restr is not None: rule.update(self._restriction(restr, ns))
            if attr.get("use") == "required": rule["required"] = True
            if attr.get("default"): rule["default"] = attr.get("default")
            if attr.get("fixed"):   rule["fixed"]   = attr.get("fixed")
            if rule: out["@"+name] = rule
        return out

    def _restriction(self, restr, ns) -> dict:
        if restr is None: return {}
        rule = {}
        if restr.get("base"): rule["type"] = restr.get("base").replace("xs:","")
        enums = [e.get("value") for e in restr.findall("xs:enumeration",ns) if e.get("value")]
        if enums: rule["enum"] = enums
        for facet, key in [("xs:minInclusive","min"),("xs:maxInclusive","max"),
                            ("xs:minLength","minLength"),("xs:maxLength","maxLength"),
                            ("xs:totalDigits","totalDigits"),("xs:fractionDigits","fractionDigits")]:
            el = restr.find(facet, ns)
            if el is not None: rule[key] = el.get("value")
        pat = restr.find("xs:pattern", ns)
        if pat is not None: rule["pattern"] = pat.get("value")
        return rule

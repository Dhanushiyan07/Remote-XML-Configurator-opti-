import re

class Validator:
    def validate(self, rule: dict, value: str):
        try:
            dtype = rule.get("type", "string").lower()
            value = str(value).strip()

            if rule.get("required") and not value:
                return False, "This field is required."
            if dtype in ("boolean", "bool") and value.lower() not in ("true","false","1","0"):
                return False, "Value must be true, false, 1 or 0."
            if dtype in ("int", "integer"):
                try: int(value)
                except ValueError: return False, f"'{value}' is not a valid integer."
            if dtype in ("float", "double", "decimal"):
                try: float(value)
                except ValueError: return False, f"'{value}' is not a valid number."
            if "enum" in rule and value not in rule["enum"]:
                return False, f"Value must be one of: {', '.join(rule['enum'])}"
            if "min" in rule:
                try:
                    if float(value) < float(rule["min"]): return False, f"Value must be >= {rule['min']}."
                except ValueError: pass
            if "max" in rule:
                try:
                    if float(value) > float(rule["max"]): return False, f"Value must be <= {rule['max']}."
                except ValueError: pass
            if "minLength" in rule and len(value) < int(rule["minLength"]):
                return False, f"Minimum length is {rule['minLength']} characters."
            if "maxLength" in rule and len(value) > int(rule["maxLength"]):
                return False, f"Maximum length is {rule['maxLength']} characters."
            if "pattern" in rule and not re.fullmatch(rule["pattern"], value):
                return False, f"Value does not match required pattern: {rule['pattern']}"
            if "fixed" in rule and value != str(rule["fixed"]):
                return False, f"This field has a fixed value of '{rule['fixed']}'."
            if "totalDigits" in rule:
                if len(value.replace(".","").replace("-","")) > int(rule["totalDigits"]):
                    return False, f"Maximum {rule['totalDigits']} significant digits allowed."
            if "fractionDigits" in rule and "." in value:
                if len(value.split(".")[1]) > int(rule["fractionDigits"]):
                    return False, f"Maximum {rule['fractionDigits']} decimal places allowed."
            return True, ""
        except Exception as e:
            return False, f"Validation error: {e}"

    def infer_type(self, value: str) -> str:
        v = str(value).strip()
        if v.lower() in ("true", "false"): return "boolean"
        try: int(v); return "integer"
        except ValueError: pass
        try: float(v); return "float"
        except ValueError: pass
        return "string"

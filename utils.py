import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rapidfuzz import process, fuzz

VALID_INCOTERMS = {"FOB", "CIF", "CFR", "EXW", "DDP", "DAP", "FCA", "CPT", "CIP", "DPU"}


def load_port_reference(path: Optional[str] = None) -> List[Dict]:
    p = Path(path) if path else Path(__file__).parent / "port_codes_reference.json"
    return json.loads(p.read_text(encoding="utf-8"))


def build_port_index(ref: List[Dict]) -> Tuple[Dict[str, str], Dict[str, str]]:
    # name->code and code->name
    name_to_code = {}
    code_to_name = {}
    for entry in ref:
        code = entry.get("code")
        name = entry.get("name")
        if not code or not name:
            continue
        code_to_name[code] = name
        name_to_code[name.lower()] = code
        # add simple tokens
        for tok in re.split(r"[\s,-/]+", name.lower()):
            if len(tok) >= 2:
                name_to_code.setdefault(tok, code)
    return name_to_code, code_to_name


def fuzzy_find_port(text: str, name_index: Dict[str, str], threshold: int = 70) -> Optional[Tuple[str, float]]:
    if not text or not name_index:
        return None
    choices = list(name_index.keys())
    match, score, _ = process.extractOne(text.lower(), choices, scorer=fuzz.WRatio) or (None, 0, None)
    if match and score >= threshold:
        return name_index[match], float(score)
    return None


def find_ports_in_text(text: str, name_index: Dict[str, str]) -> List[str]:
    # Find candidate tokens and fuzzy match
    found = []
    # Try long substrings first (n-grams)
    tokens = re.findall(r"[A-Za-z]{2,}(?:\s+[A-Za-z]{2,})*", text)
    seen_codes = set()
    for t in sorted(tokens, key=lambda s: -len(s)):
        res = fuzzy_find_port(t, name_index, threshold=75)
        if res:
            code, _ = res
            if code not in seen_codes:
                found.append(code)
                seen_codes.add(code)
    return found


def parse_incoterm(text: str) -> Optional[str]:
    if not text:
        return None
    txt = text.upper()
    found = []
    for inc in VALID_INCOTERMS:
        if re.search(r"\b" + re.escape(inc) + r"\b", txt):
            found.append(inc)
    if not found:
        return None
    # ambiguous: choose first, but if multiple choose FOB per rules
    if len(found) > 1:
        return "FOB"
    return found[0]


def parse_cbm(text: str) -> Optional[float]:
    if not text:
        return None
    # look for cbm or m3
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:cbm|m3|cubic meters|cubic metres)\b", text, re.I)
    if m:
        return float(m.group(1).replace(',', '.'))
    return None


def parse_weight_kg(text: str) -> Optional[float]:
    if not text:
        return None
    # kg
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:kg|kgs)\b", text, re.I)
    if m:
        return float(m.group(1).replace(',', '.'))
    # tonnes / mt
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:tonne|tonnes|t|mt)\b", text, re.I)
    if m:
        return float(m.group(1).replace(',', '.')) * 1000.0
    # lbs
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:lb|lbs)\b", text, re.I)
    if m:
        return float(m.group(1).replace(',', '.')) * 0.453592
    # zero explicit
    if re.search(r"\b0\s*(?:kg|kgs|lb|lbs|tonne|t|mt)\b", text):
        return 0.0
    # TBD / N/A
    if re.search(r"\b(?:TBD|N/A|TO BE CONFIRMED|TO BE ADVISED)\b", text, re.I):
        return None
    return None


def detect_dangerous(text: str) -> bool:
    if not text:
        return False
    txt = text.lower()
    negatives = ["non-hazardous", "non hazardous", "non-dg", "not dangerous", "non dg"]
    for n in negatives:
        if n in txt:
            return False
    keywords = ["dg", "dangerous", "hazardous", r"class \d", "imo", "imdg"]
    for k in keywords:
        if re.search(k, txt):
            return True
    return False


def choose_product_line(origin_code: Optional[str], dest_code: Optional[str]) -> Optional[str]:
    # Business rule: destination IN -> import; origin IN -> export; all LCL
    if dest_code and dest_code.upper().startswith("IN"):
        return "pl_sea_import_lcl"
    if origin_code and origin_code.upper().startswith("IN"):
        return "pl_sea_export_lcl"
    return None

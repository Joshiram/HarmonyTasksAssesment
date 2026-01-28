BASE_PROMPT = """
Extract shipment details from the email. Return a JSON object with keys:
id, product_line, origin_port_code, origin_port_name, destination_port_code, destination_port_name, incoterm, cargo_weight_kg, cargo_cbm, is_dangerous

Follow these rules:
- Use UN/LOCODE for ports when possible; if unknown set code and name to null.
- Normalize incoterm to uppercase; default to FOB if missing or ambiguous.
- Numeric fields: round to 2 decimals; missing -> null; explicit 0 allowed.
- Detect dangerous goods using keywords; negations ("non-dangerous") mean false.
"""

# Example prompt (v1->v3 evolution should be stored here in real submission)
EXTRA_PROMPT_EXAMPLE = "v1: simple extraction; v2: added port code mapping; v3: added conflict-resolution and defaults"

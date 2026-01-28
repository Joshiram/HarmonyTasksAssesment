"""Main extraction script.
Usage: python extract.py [--mock]
--mock: use local rule-based extractor instead of calling Groq API (useful for offline testing)
"""
import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from schemas import ExtractionResult
from utils import (
    build_port_index,
    choose_product_line,
    detect_dangerous,
    find_ports_in_text,
    load_port_reference,
    parse_cbm,
    parse_incoterm,
    parse_weight_kg,
)

try:
    from groq import Groq
except Exception:
    Groq = None

load_dotenv()
logger = logging.getLogger("extract")
logging.basicConfig(level=logging.INFO)


def call_llm(prompt: str, retries: int = 3, temperature: float = 0.0) -> Optional[str]:
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
    if not api_key or Groq is None:
        logger.warning("Groq not configured or client missing; cannot call LLM")
        return None
    client = Groq(api_key=api_key)
    attempt = 0
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

    @retry(stop=stop_after_attempt(retries), wait=wait_exponential(min=1, max=10))
    def _call():
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return resp

    try:
        r = _call()
        return str(r)
    except Exception as e:
        logger.exception("LLM call failed: %s", e)
        return None


def rule_extract(email: Dict[str, str], name_index: Dict[str, str], code_to_name: Dict[str, str]) -> Dict[str, Any]:
    subj = email.get("subject", "")
    body = email.get("body", "")
    combined = subj + "\n" + body

    # Ports: prefer body over subject per rules
    body_ports = find_ports_in_text(body, name_index)
    subj_ports = find_ports_in_text(subj, name_index)
    ports = body_ports or subj_ports

    origin = ports[0] if len(ports) >= 1 else None
    dest = ports[1] if len(ports) >= 2 else None

    incoterm = parse_incoterm(body) or parse_incoterm(subj) or "FOB"
    cbm = parse_cbm(body) or parse_cbm(subj)
    weight = parse_weight_kg(body) or parse_weight_kg(subj)
    dangerous = detect_dangerous(combined)
    product_line = choose_product_line(origin, dest)

    return {
        "id": email.get("id"),
        "product_line": product_line,
        "origin_port_code": origin,
        "origin_port_name": code_to_name.get(origin) if origin else None,
        "destination_port_code": dest,
        "destination_port_name": code_to_name.get(dest) if dest else None,
        "incoterm": incoterm,
        "cargo_weight_kg": weight,
        "cargo_cbm": cbm,
        "is_dangerous": dangerous,
    }


def main(mock: bool = False):
    root = Path(__file__).parent
    emails_path = root / "emails_input.json"
    ports_ref = load_port_reference(root / "port_codes_reference.json")
    name_index, code_to_name = build_port_index(ports_ref)

    emails = json.loads(emails_path.read_text(encoding="utf-8"))
    outputs = []
    for email in emails:
        try:
            if mock:
                raw = rule_extract(email, name_index, code_to_name)
            else:
                # build prompt (simple for now) and call LLM
                prompt = f"{email.get('subject')}\n\n{email.get('body')}\n\n{''}"
                llm_resp = call_llm(prompt, retries=int(os.getenv("MAX_RETRIES", 3)), temperature=float(os.getenv("GROQ_TEMPERATURE", 0)))
                if llm_resp:
                    # Try to parse JSON block from response
                    import re

                    m = re.search(r"\{[\s\S]*\}", llm_resp)
                    if m:
                        raw = json.loads(m.group(0))
                    else:
                        logger.warning("LLM returned no JSON; falling back to rules for id=%s", email.get("id"))
                        raw = rule_extract(email, name_index, code_to_name)
                else:
                    raw = rule_extract(email, name_index, code_to_name)

            # Validate and normalize through Pydantic
            validated = ExtractionResult(**raw)
            outputs.append(validated.dict())
        except Exception as e:
            logger.exception("Failed to extract for email %s: %s", email.get("id"), e)
            # Per README: include record with nulls on failure
            outputs.append(
                ExtractionResult(
                    id=email.get("id"),
                    product_line=None,
                    origin_port_code=None,
                    origin_port_name=None,
                    destination_port_code=None,
                    destination_port_name=None,
                    incoterm=None,
                    cargo_weight_kg=None,
                    cargo_cbm=None,
                    is_dangerous=False,
                ).dict()
            )

    out_path = root / "output.json"
    out_path.write_text(json.dumps(outputs, indent=2), encoding="utf-8")
    print(f"Wrote {len(outputs)} records to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use rule-based extractor instead of Groq")
    args = parser.parse_args()
    main(mock=args.mock)

import json
from pathlib import Path
from typing import Any, Dict, List

from schemas import ExtractionResult


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def compare_field(a: Any, b: Any) -> bool:
    # Null handling
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # Floats: compare rounded to 2 decimals
    if isinstance(a, float) or isinstance(b, float):
        try:
            return round(float(a), 2) == round(float(b), 2)
        except Exception:
            return False
    # Strings: case-insensitive trimmed
    try:
        return str(a).strip().lower() == str(b).strip().lower()
    except Exception:
        return False


def evaluate(output_path: Path, truth_path: Path):
    out = load_json(output_path)
    truth = load_json(truth_path)
    truth_map = {t["id"]: t for t in truth}

    fields = [
        "product_line",
        "origin_port_code",
        "origin_port_name",
        "destination_port_code",
        "destination_port_name",
        "incoterm",
        "cargo_weight_kg",
        "cargo_cbm",
        "is_dangerous",
    ]

    totals = {f: 0 for f in fields}
    correct = {f: 0 for f in fields}
    total_values = 0
    correct_values = 0

    for rec in out:
        id = rec.get("id")
        gold = truth_map.get(id)
        if not gold:
            continue
        for f in fields:
            totals[f] += 1
            total_values += 1
            if compare_field(rec.get(f), gold.get(f)):
                correct[f] += 1
                correct_values += 1

    # Print metrics
    print("Per-field accuracy:")
    for f in fields:
        acc = correct[f] / totals[f] * 100 if totals[f] else 0.0
        print(f"- {f}: {acc:.2f}% ({correct[f]}/{totals[f]})")
    overall = correct_values / total_values * 100 if total_values else 0.0
    print(f"Overall accuracy: {overall:.2f}% ({correct_values}/{total_values})")


if __name__ == "__main__":
    root = Path(__file__).parent
    evaluate(root / "output.json", root / "ground_truth.json")

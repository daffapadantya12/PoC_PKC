#!/usr/bin/env python3
import argparse
import csv
import json
import os
from typing import Any, Dict

COLUMNS = [
    "timestamp",
    "session_id",
    "type",
    "user_input",
    "ai_response",
    "action",
    "details",
]


def normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure consistent columns and flatten details.
    - details dict is serialized as JSON string.
    - missing fields become empty strings (better for Excel).
    """
    out: Dict[str, Any] = {}
    out["timestamp"] = entry.get("timestamp", "")
    out["session_id"] = entry.get("session_id", "")
    out["type"] = entry.get("type", "")
    out["user_input"] = entry.get("user_input", "") or ""
    out["ai_response"] = entry.get("ai_response", "") or ""
    out["action"] = entry.get("action", "") or ""
    details = entry.get("details", "")
    if isinstance(details, (dict, list)):
        out["details"] = json.dumps(details, ensure_ascii=False)
    else:
        out["details"] = details if details is not None else ""
    return out


def export_file(input_path: str, output_path: str, excel_utf8_bom: bool = False) -> int:
    """Convert a JSONL session file to CSV. Returns number of rows written."""
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Choose encoding: Excel-friendly UTF-8 BOM if requested
    encoding = "utf-8-sig" if excel_utf8_bom else "utf-8"

    rows = 0
    with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "w", newline="", encoding=encoding) as fout:
        writer = csv.DictWriter(fout, fieldnames=COLUMNS)
        writer.writeheader()
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines, but keep going
                continue
            writer.writerow(normalize_entry(obj))
            rows += 1
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export dialogue JSONL session to CSV (Excel-ready)")
    parser.add_argument("input", help="Path to JSONL session file")
    parser.add_argument("-o", "--output", help="Output CSV path (defaults to <input>.csv)")
    parser.add_argument("--excel", action="store_true", help="Write CSV as UTF-8 with BOM for Excel")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if args.output:
        output_path = os.path.abspath(args.output)
    else:
        base, _ = os.path.splitext(input_path)
        output_path = base + ".csv"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    rows = export_file(input_path, output_path, excel_utf8_bom=args.excel)
    print(f"Wrote {rows} rows to {output_path}")


if __name__ == "__main__":
    main()
"""Parse the actual SOP .doc file into structured JSON rules.

Uses Word COM automation (Windows) to extract text from the old-format .doc,
then parses the step/branch structure into the same JSON schema used by the
rules engine.

Usage:
    python scripts/parse_sop_from_doc.py
"""

from __future__ import annotations

import json
import os
import re
import sys


def extract_text_via_com(doc_path: str) -> dict:
    """Extract paragraphs and table cells from a .doc file via Word COM."""
    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(os.path.abspath(doc_path))

        # Extract main table (Table 2 = the SOP exception matrix)
        table_data: dict[int, dict[str, str]] = {}
        if doc.Tables.Count >= 2:
            table = doc.Tables(2)
            for r in range(2, table.Rows.Count + 1):  # skip header row
                row: dict[str, str] = {}
                for c in range(1, table.Columns.Count + 1):
                    try:
                        cell_text = table.Cell(r, c).Range.Text
                        # Clean control chars
                        cell_text = cell_text.replace("\x07", "").replace("\x01", "").strip()
                        row[c] = cell_text
                    except Exception:
                        row[c] = ""
                table_data[r] = row

        doc.Close(False)
        return table_data
    finally:
        word.Quit()


def parse_identity_steps(raw_text: str) -> dict:
    """Parse Identity exception steps from the ECM cell text."""
    decline_flow = []
    refer_flow = []

    # Split by "Decline" and "Refer" sections
    parts = re.split(r"(Decline.*?Follow the below steps\.|Refer.*?Follow the below steps\.)", raw_text, flags=re.DOTALL)

    current_section = None
    for part in parts:
        if "Decline" in part:
            current_section = "decline"
            continue
        elif "Refer" in part:
            current_section = "refer"
            continue

        if current_section == "decline":
            steps = re.findall(r"Step\s+(\w+):\s*(.+?)(?=Step|\Z)", part, re.DOTALL)
            for step_id, action in steps:
                action = action.strip().rstrip("\r\n")
                entry: dict = {}

                if re.match(r"^\d+$", step_id):
                    entry["step"] = int(step_id)
                else:
                    entry["branch"] = step_id

                if "If matched" in action or "If not matched" in action or "Not matched" in action:
                    if "If matched" in action:
                        entry["condition"] = "Matched"
                    else:
                        entry["condition"] = "Not matched"

                entry["action"] = action
                if "Completed" in action:
                    entry["status"] = "Completed"
                elif "Supplement" in action:
                    entry["status"] = "SupplementRequired"

                decline_flow.append(entry)

        elif current_section == "refer":
            steps = re.findall(r"Step\s+(\w+):\s*(.+?)(?=Step|\Z)", part, re.DOTALL)
            for step_id, action in steps:
                action = action.strip().rstrip("\r\n")
                refer_flow.append({
                    "step": 1,
                    "action": action,
                    "status": "NotRequired",
                })

    return {"DeclineFlow": decline_flow, "ReferFlow": refer_flow}


def parse_address_steps(raw_text: str) -> dict:
    """Parse Address Proof exception steps from the ECM cell text."""
    decline_flow = []
    refer_flow = []

    parts = re.split(r"(Refer\s*\(not PASSED\).*?Follow the below steps\.|Refer\s*\+.*?Follow the below steps\.)", raw_text, flags=re.DOTALL)

    current_section = None
    for part in parts:
        if "not PASSED" in part:
            current_section = "decline"
            continue
        elif "Refer" in part and current_section == "decline":
            current_section = "refer"
            continue

        if current_section == "decline":
            steps = re.findall(r"Step\s+(\w+):\s*(.+?)(?=Step|\Z)", part, re.DOTALL)
            for step_id, action in steps:
                action = action.strip().rstrip("\r\n")
                entry: dict = {}

                if re.match(r"^\d+$", step_id):
                    entry["step"] = int(step_id)
                else:
                    entry["branch"] = step_id

                if "If matched" in action or "If not matched" in action or "Not matched" in action:
                    if "If matched" in action:
                        entry["condition"] = "Matched"
                    else:
                        entry["condition"] = "Not matched"

                entry["action"] = action
                if "Completed" in action:
                    entry["status"] = "Completed"
                elif "Supplement" in action:
                    entry["status"] = "SupplementRequired"

                decline_flow.append(entry)

        elif current_section == "refer":
            steps = re.findall(r"Step\s+(\w+):\s*(.+?)(?=Step|\Z)", part, re.DOTALL)
            for step_id, action in steps:
                action = action.strip().rstrip("\r\n")
                refer_flow.append({
                    "step": 1,
                    "action": action,
                    "status": "NotRequired",
                })

    return {"DeclineFlow": decline_flow, "ReferFlow": refer_flow}


def parse_nns_steps(raw_text: str) -> dict:
    """Parse NNS exception steps from the ECM cell text."""
    flow = []

    steps = re.findall(r"Step\s+(\w+):\s*(.+?)(?=Step|\Z)", raw_text, re.DOTALL)
    for step_id, action in steps:
        action = action.strip().rstrip("\r\n")
        entry: dict = {}

        if re.match(r"^\d+$", step_id):
            entry["step"] = int(step_id)
        else:
            entry["branch"] = step_id

        if "If Proceed" in action:
            entry["condition"] = "Proceed"
        elif "If Remediate" in action:
            entry["condition"] = "Remediate first"
        elif "If Not Matched" in action:
            entry["condition"] = "No match"
        elif "If Potential Match" in action:
            entry["condition"] = "Potential match"

        entry["action"] = action
        if "Completed" in action:
            entry["status"] = "Completed"
        elif "investigation required" in action.lower():
            entry["status"] = "InvestigationRequired"

        flow.append(entry)

    # Extract country routing from the embedded sub-table in step 3B
    # The sub-table appears as \r-delimited pairs: "Country\rTeam\r\rCountry\rTeam"
    routing = {}
    # Find the embedded table text after "following table"
    table_match = re.search(r"following table\r+(.*)", raw_text, re.DOTALL)
    if table_match:
        table_text = table_match.group(1)
        # Skip header row ("Country issuing...\rCountry Team\r")
        rows = [r.strip() for r in re.split(r"\r\r+", table_text) if r.strip()]
        for row in rows:
            parts = [p.strip() for p in row.split("\r") if p.strip()]
            if len(parts) == 2:
                country, team_str = parts
                if country.lower() in ("country issuing the identity document", "country team"):
                    continue
                team_region = "APAC" if "APAC" in team_str else ("EMEA" if "EMEA" in team_str else "AMERICAS")
                routing[country] = team_region

    return {"DeclineFlow": flow, "ReferFlow": flow, "CountryRouting": routing}


def main():
    doc_path = r"C:\Users\sharmadeep\kyc-automation\data\SOP - International Account Opening.docx"
    output_path = r"C:\Users\sharmadeep\kyc-automation\data\sop_rules\sop_rules_parsed.json"

    print(f"Parsing SOP document: {doc_path}")
    table_data = extract_text_via_com(doc_path)

    rules: dict = {}

    for row_num, row in table_data.items():
        exception_type = row.get(2, "").strip()
        ecm_text = row.get(4, "")

        if "Identity" in exception_type:
            print(f"  Parsing Identity exception (row {row_num})...")
            rules["Identity"] = parse_identity_steps(ecm_text)
        elif "Address" in exception_type:
            print(f"  Parsing Address Proof exception (row {row_num})...")
            rules["AddressProof"] = parse_address_steps(ecm_text)
        elif "NNS" in exception_type:
            print(f"  Parsing NNS exception (row {row_num})...")
            nns = parse_nns_steps(ecm_text)
            rules["NNS"] = {"DeclineFlow": nns["DeclineFlow"], "ReferFlow": nns["ReferFlow"]}
            rules["NNS_CountryRouting"] = nns["CountryRouting"]

    # Write output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

    print(f"\nParsed rules written to: {output_path}")
    print(json.dumps(rules, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()

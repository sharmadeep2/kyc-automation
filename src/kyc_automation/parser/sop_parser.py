"""SOP Document Parser — uses Azure Document Intelligence to extract
structured rules from the SOP Word document.

This module is used during the *setup* phase to convert the SOP .docx
into the machine-readable JSON consumed by the rules engine.  At runtime
the agents use the pre-parsed JSON directly.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def parse_sop_document(file_path: str | Path) -> dict[str, Any]:
    """Parse an SOP document using Azure Document Intelligence.

    Args:
        file_path: Path to the SOP .docx or .pdf file.

    Returns:
        A dictionary of extracted content (paragraphs, tables, key-value pairs).
    """
    endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint or not key:
        raise EnvironmentError(
            "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
            "AZURE_DOCUMENT_INTELLIGENCE_KEY environment variables."
        )

    # Lazy import so the SDK is only required when actually parsing
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential

    client = DocumentAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )

    file_path = Path(file_path)
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", document=f)
    result = poller.result()

    extracted: dict[str, Any] = {
        "paragraphs": [],
        "tables": [],
    }

    # Extract paragraphs (including bold step instructions)
    for paragraph in result.paragraphs:
        extracted["paragraphs"].append({
            "role": getattr(paragraph, "role", None),
            "content": paragraph.content,
        })

    # Extract tables (e.g. country-to-team routing)
    for table in result.tables:
        rows: list[list[str]] = []
        current_row: list[str] = []
        current_row_idx = -1
        for cell in table.cells:
            if cell.row_index != current_row_idx:
                if current_row:
                    rows.append(current_row)
                current_row = []
                current_row_idx = cell.row_index
            current_row.append(cell.content)
        if current_row:
            rows.append(current_row)
        extracted["tables"].append(rows)

    logger.info("Extracted %d paragraphs and %d tables from %s",
                len(extracted["paragraphs"]), len(extracted["tables"]), file_path.name)
    return extracted


def save_extracted(extracted: dict[str, Any], output_path: str | Path) -> None:
    """Save extracted content to a JSON file for review / further processing."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    logger.info("Saved extracted content to %s", output_path)

import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows
from ..models import PropertyRecord

logger = logging.getLogger(__name__)


def export_excel(records: List[PropertyRecord], exceptions: List[Dict], summary: Dict[str, int], output_path: Path):
    """Export to Excel with multiple sheets."""
    logger.info(f"Exporting Excel to {output_path}")

    # 1. Properties sheet
    data = [rec.model_dump(exclude={"raw_values"}) for rec in records]
    df_props = pd.DataFrame(data)
    # Remove empty columns
    df_props.dropna(axis=1, how="all", inplace=True)

    # 2. Exceptions sheet
    df_exc = pd.DataFrame(exceptions)

    # 3. QA Summary
    df_qa = pd.DataFrame([summary])

    # 4. Data Dictionary (from mapping config – placeholder)
    df_dict = pd.DataFrame([
        {"Column": "record_id", "Description": "Unique identifier"},
        {"Column": "total_assessment", "Description": "Total assessed value"},
    ])

    # 5. Source Metadata
    df_meta = pd.DataFrame([
        {"Key": "Publisher", "Value": "MAMH, Gouvernement du Québec"},
        {"Key": "License", "Value": "CC BY 4.0"},
        {"Key": "Source", "Value": "Rôle d'évaluation foncière du Québec"},
    ])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_props.to_excel(writer, sheet_name="Properties", index=False)
        df_exc.to_excel(writer, sheet_name="Exceptions", index=False)
        df_qa.to_excel(writer, sheet_name="QA Summary", index=False)
        df_dict.to_excel(writer, sheet_name="Data Dictionary", index=False)
        df_meta.to_excel(writer, sheet_name="Source Metadata", index=False)

    # Apply formatting (autofilter, freeze panes, etc.)
    wb = writer.book
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        # Autofilter
        ws.auto_filter.ref = ws.dimensions
        # Freeze first row
        ws.freeze_panes = "A2"
        # Bold headers
        for cell in ws[1]:
            cell.font = Font(bold=True)
        # Adjust column widths
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

    logger.info("Excel export complete")
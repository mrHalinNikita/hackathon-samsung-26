from pathlib import Path
import openpyxl

from src.parsers.base import BaseParser, ParsedContent


class XlsxParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".xlsx", ".xlsm"]
    
    async def parse(self, filepath: Path) -> ParsedContent:
        text_parts = []
        metadata = {"path": str(filepath), "sheets": []}
        
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                sheet_text = []
                
                for row in sheet.iter_rows(values_only=True):
                    row_values = [str(cell) if cell is not None else "" for cell in row]

                    if any(v.strip() for v in row_values):
                        sheet_text.append("\t".join(row_values))
                
                if sheet_text:
                    text_parts.append(f"[Лист: {sheet_name}]\n" + "\n".join(sheet_text))
                    metadata["sheets"].append({
                        "name": sheet_name,
                        "rows": sheet.max_row,
                        "columns": sheet.max_column,
                    })
        
        except Exception as e:
            return ParsedContent(
                text="",
                metadata=metadata,
                errors=[f"XLSX parse error: {e}"],
            )
        
        full_text = "\n\n".join(text_parts)
        
        return ParsedContent(
            text=full_text,
            metadata=metadata,
            word_count=len(full_text.split()),
            char_count=len(full_text),
        )
from pathlib import Path
import pdfplumber

from src.parsers.base import BaseParser, ParsedContent


class PdfParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]
    
    async def parse(self, filepath: Path) -> ParsedContent:
        text_parts = []
        metadata = {"path": str(filepath), "pages": 0}
        errors = []
        
        try:
            with pdfplumber.open(filepath) as pdf:
                metadata["pages"] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"[Страница {page_num}]\n{page_text}")
                    
                    if page_num == 1 and pdf.metadata:
                        metadata.update({
                            "author": pdf.metadata.get("Author"),
                            "title": pdf.metadata.get("Title"),
                            "subject": pdf.metadata.get("Subject"),
                            "creator": pdf.metadata.get("Creator"),
                        })
        
        except Exception as e:
            errors.append(f"PDF parse error: {e}")

            try:
                import PyPDF2
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
            except:
                pass
        
        full_text = "\n\n".join(text_parts)
        
        return ParsedContent(
            text=full_text,
            metadata=metadata,
            errors=errors,
            word_count=len(full_text.split()),
            char_count=len(full_text),
        )
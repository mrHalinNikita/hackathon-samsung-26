from pathlib import Path
from bs4 import BeautifulSoup
import html2text

from src.parsers.base import BaseParser, ParsedContent


class HtmlParser(BaseParser):
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".html", ".htm"]
    
    async def parse(self, filepath: Path) -> ParsedContent:
        try:
            html_content = self._read_file_text(filepath)
            soup = BeautifulSoup(html_content, "lxml")
            
            for tag in soup(["script", "style", "meta", "noscript"]):
                tag.decompose()
            
            text = html2text.html2text(str(soup), bodywidth=0)
            
            metadata = {"path": str(filepath)}
            title = soup.find("title")
            if title:
                metadata["title"] = title.get_text(strip=True)
            
            return ParsedContent(text=text.strip(), metadata=metadata, word_count=len(text.split()), char_count=len(text))
        
        except Exception as e:
            return ParsedContent(text="", metadata={"path": str(filepath)}, errors=[f"HTML parse error: {e}"])
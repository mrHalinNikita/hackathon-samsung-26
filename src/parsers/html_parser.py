from pathlib import Path

from bs4 import BeautifulSoup, Comment

from src.parsers.base import BaseParser, ParsedContent


class HtmlParser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".html", ".htm"]

    async def parse(self, filepath: Path) -> ParsedContent:
        try:
            html_content = self._read_file_text(filepath)
            soup = BeautifulSoup(html_content, "lxml")

            for tag in soup(["script", "style", "meta", "noscript", "svg"]):
                tag.decompose()

            for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
                c.extract()

            for tag_name in ["footer", "nav"]:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            visible_text = soup.get_text("\n", strip=True)
            lines = [line for line in (x.strip() for x in visible_text.splitlines()) if line]

            metadata = {"path": str(filepath), "parser_mode": "visible_text_only"}
            title = soup.find("title")
            if title:
                metadata["title"] = title.get_text(strip=True)

            text = "\n".join(lines)
            return ParsedContent(text=text, metadata=metadata, word_count=len(text.split()), char_count=len(text))
        except Exception as e:
            return ParsedContent(text="", metadata={"path": str(filepath)}, errors=[f"HTML parse error: {e}"])

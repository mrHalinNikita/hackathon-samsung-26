from pathlib import Path

from src.parsers.base import BaseParser, ParsedContent


class Mp4Parser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".mp4"]

    async def parse(self, filepath: Path) -> ParsedContent:
        # Conservative mode: no OCR over all frames by default.
        return ParsedContent(
            text="",
            metadata={"path": str(filepath), "parser_mode": "conservative_mp4"},
            errors=["MP4 parsing is conservative and disabled by default"],
        )

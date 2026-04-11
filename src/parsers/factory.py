from pathlib import Path
from typing import Type
import structlog

from src.parsers.base import BaseParser, ParsedContent
from src.parsers.txt_parser import TxtParser
from src.parsers.csv_parser import CsvParser
from src.parsers.json_parser import JsonParser
from src.parsers.html_parser import HtmlParser
from src.parsers.pdf_parser import PdfParser
from src.parsers.docx_parser import DocxParser
from src.parsers.xlsx_parser import XlsxParser
from src.parsers.image_parser import ImageParser

logger = structlog.get_logger("parser_factory")


class ParserFactory:
    
    _parsers: dict[str, Type[BaseParser]] = {}
    
    @classmethod
    def register(cls, parser_class: Type[BaseParser]) -> None:

        instance = parser_class()
        for ext in instance.supported_extensions:
            cls._parsers[ext.lower()] = parser_class
            logger.debug("Parser registered", extension=ext, parser=parser_class.__name__)
    
    @classmethod
    def _init_parsers(cls) -> None:

        if cls._parsers:
            return
        
        for parser_cls in [
            TxtParser, CsvParser, JsonParser, HtmlParser,
            PdfParser, DocxParser, XlsxParser, ImageParser,
        ]:
            cls.register(parser_cls)
    
    @classmethod
    def get_parser(cls, filepath: Path) -> BaseParser | None:

        cls._init_parsers()
        ext = filepath.suffix.lower()
        parser_cls = cls._parsers.get(ext)
        
        if parser_cls:
            return parser_cls()
        
        logger.warning("No parser found for extension", extension=ext, path=str(filepath))
        return None
    
    @classmethod
    async def parse_file(cls, filepath: Path) -> ParsedContent | None:

        parser = cls.get_parser(filepath)
        if not parser:
            return None
        
        try:
            return await parser.parse(filepath)
        except Exception as e:
            logger.error("Error parsing file", path=str(filepath), error=str(e), error_type=type(e).__name__,)
            return ParsedContent(text="", metadata={"path": str(filepath)},errors=[f"{type(e).__name__}: {e}"],)
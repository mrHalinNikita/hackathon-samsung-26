from pathlib import Path

from src.parsers.base import BaseParser, ParsedContent


class ParquetParser(BaseParser):
    @property
    def supported_extensions(self) -> list[str]:
        return [".parquet"]

    async def parse(self, filepath: Path) -> ParsedContent:
        metadata = {"path": str(filepath), "parser_mode": "structured"}
        try:
            import pandas as pd

            df = pd.read_parquet(filepath)
            lines = []
            for idx, row in df.iterrows():
                pairs = [f"{col}: {row[col]}" for col in df.columns if str(row[col]) != "nan"]
                if pairs:
                    lines.append(f"ROW[{idx}] | " + " | ".join(pairs))
            text = "\n".join(lines)
            metadata["rows"] = len(df)
            metadata["columns"] = len(df.columns)
            return ParsedContent(text=text, metadata=metadata, word_count=len(text.split()), char_count=len(text))
        except Exception as e:
            return ParsedContent(text="", metadata=metadata, errors=[f"Parquet parse error: {e}"])

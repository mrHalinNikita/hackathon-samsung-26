import os
import hashlib
from pathlib import Path
from typing import Iterator, Optional
from dataclasses import dataclass
import structlog

from src.config import settings

logger = structlog.get_logger("scanner")


@dataclass(frozen=True)
class FileInfo:
    
    path: Path
    size_bytes: int
    extension: str
    file_hash: Optional[str] = None
    
    @property
    def is_supported(self) -> bool:
        return self.extension.lower() in settings.SCAN_SUPPORTED_EXTENSIONS
    
    @property
    def is_too_large(self) -> bool:
        max_bytes = settings.SCAN_MAX_FILE_SIZE_MB * 1024 * 1024
        return self.size_bytes > max_bytes


def calculate_file_hash(filepath: Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str:

    hasher = hashlib.new(algorithm)
    
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def walk_directory(root_path: str, calculate_hash: bool = False, follow_symlinks: bool = False,) -> Iterator[FileInfo]:

    root = Path(root_path).resolve()
    
    if not root.exists():
        logger.error("Directory not found", path=str(root))
        return
    
    if not root.is_dir():
        logger.error("The specified path is not a directory", path=str(root))
        return
    
    logger.info("Start scanning a directory", path=str(root), hash_calc=calculate_hash)
    
    scanned = 0
    matched = 0
    skipped = 0
    
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        
        for filename in filenames:
            if filename.startswith('.'):
                skipped += 1
                continue
            
            filepath = Path(dirpath) / filename
            
            try:
                stat = filepath.stat()
            except (OSError, PermissionError) as e:
                logger.warning("Failed to get file metadata", path=str(filepath), error=str(e))
                skipped += 1
                continue
            
            file_info = FileInfo(path=filepath, size_bytes=stat.st_size, extension=filepath.suffix)
            
            if not file_info.is_supported:
                skipped += 1
                continue
            
            if file_info.is_too_large:
                logger.warning(
                    "File exceeds size limit",
                    path=str(filepath),
                    size_mb=file_info.size_bytes / 1024 / 1024,
                    limit_mb=settings.SCAN_MAX_FILE_SIZE_MB,
                )
                skipped += 1
                continue
            
            if calculate_hash:
                try:
                    file_hash = calculate_file_hash(filepath)
                    file_info = FileInfo(
                        path=file_info.path,
                        size_bytes=file_info.size_bytes,
                        extension=file_info.extension,
                        file_hash=file_hash,
                    )
                except (OSError, PermissionError) as e:
                    logger.warning("Failed to calculate file hash", path=str(filepath), error=str(e))
                    skipped += 1
                    continue
            
            matched += 1
            yield file_info
            scanned += 1
    
    logger.info("Scanning complete", path=str(root), scanned=scanned, matched=matched, skipped=skipped)
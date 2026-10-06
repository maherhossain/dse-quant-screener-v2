"""Filesystem paths for the project.
All paths derive from this file's location so the code works on any machine
(office desktop, laptop) without editing. No absolute paths should appear in
any other module — import from here instead.
"""
from pathlib import Path
# src/paths.py -> parents[0] = src/, parents[1] = project root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
# Directories
SRC_DIR: Path = PROJECT_ROOT / "src"
SQL_DIR: Path = PROJECT_ROOT / "sql"
AUDIT_DIR: Path = PROJECT_ROOT / "audit"
AUDIT_RAW_DIR: Path = AUDIT_DIR / "raw"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
# Files
ENV_FILE: Path = PROJECT_ROOT / ".env"
def ensure_dirs() -> None:
    """Create writable directories if they don't exist.
    Safe to call repeatedly. Called at the top of any script that writes
    to LOGS_DIR or AUDIT_RAW_DIR. We do not create SQL_DIR or SRC_DIR —
    those are committed and must already exist.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_RAW_DIR.mkdir(parents=True, exist_ok=True)
__all__ = [
    "PROJECT_ROOT",
    "SRC_DIR",
    "SQL_DIR",
    "AUDIT_DIR",
    "AUDIT_RAW_DIR",
    "LOGS_DIR",
    "ENV_FILE",
    "ensure_dirs",
]
from __future__ import annotations

import logging
import os
from pathlib import Path


LOGGER = logging.getLogger(__name__)
WEASYPRINT_AVAILABLE = False


def render_pdf(html_path: Path, pdf_path: Path) -> bool:
    try:
        msys2_ucrt64_bin = Path("C:/msys64/ucrt64/bin")
        if os.name == "nt" and msys2_ucrt64_bin.exists():
            os.add_dll_directory(str(msys2_ucrt64_bin))
        from weasyprint import HTML
    except (ImportError, OSError):
        LOGGER.warning("WeasyPrint is unavailable. Skipping PDF rendering.")
        return False

    try:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        global WEASYPRINT_AVAILABLE
        WEASYPRINT_AVAILABLE = True
        return True
    except Exception:
        LOGGER.exception("PDF rendering failed.")
        return False

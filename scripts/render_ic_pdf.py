from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporting.config import load_reporting_config
from src.reporting.pdf_renderer import WEASYPRINT_AVAILABLE, render_pdf


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


if __name__ == "__main__":
    cfg = load_reporting_config()
    html = cfg.latest_folder / "investment_committee_report.html"
    pdf = cfg.latest_folder / "investment_committee_report.pdf"
    rendered = render_pdf(html, pdf)
    if not rendered:
        logging.info("PDF rendering skipped; WeasyPrint or its native rendering libraries are unavailable.")
    else:
        logging.info("PDF written to %s. WeasyPrint available=%s", pdf, WEASYPRINT_AVAILABLE)

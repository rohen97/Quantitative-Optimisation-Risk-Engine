from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboards.ic_dashboard import STREAMLIT_AVAILABLE, load_report_bundle


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


if __name__ == "__main__":
    bundle = load_report_bundle()
    summary = bundle.get("executive_summary", {})
    logging.info("Streamlit available: %s", STREAMLIT_AVAILABLE)
    logging.info(
        "Dashboard report bundle check loaded sections=%s; dominant regime=%s",
        len(bundle),
        summary.get("dominant_regime") if isinstance(summary, dict) else "Unavailable",
    )

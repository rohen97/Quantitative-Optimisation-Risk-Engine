from __future__ import annotations

import sys

from run_production_pipeline import main, parse_arguments


if __name__ == "__main__":
    sys.argv.extend(["--mode", "daily"]) if "--mode" not in sys.argv else None
    sys.exit(main())

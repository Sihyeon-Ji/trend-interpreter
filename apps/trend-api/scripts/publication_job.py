"""Publish one explicitly selected approved batch without migrations or model calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.storage import db, publications  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", default=os.environ.get("PUBLICATION_BATCH_ID", ""))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", args.batch_id):
        raise SystemExit("explicit_batch_id_required")
    con = None
    try:
        con = db.connect_existing()
        result = publications.publish(con, args.batch_id)
        print(json.dumps(result, sort_keys=True))
    except publications.PublicationError as exc:
        raise SystemExit(exc.code) from None
    except RuntimeError as exc:
        code = str(exc)
        raise SystemExit(code if code in {"publication_database_unavailable", "publication_schema_not_ready"}
                         else "publication_job_failed") from None
    except Exception:
        raise SystemExit("publication_job_failed") from None
    finally:
        if con is not None:
            con.close()


if __name__ == "__main__":
    main()

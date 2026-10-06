"""Stage immutable review batches and atomically publish approved changes."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.auth import check_account  # noqa: E402
from trend_agents.storage import db, publications as pub  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage")
    stage.add_argument("--file", type=Path, required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--batch-id", required=True)
    inspect.add_argument("--out", type=Path, required=True, help="Write full review data to a private file only")
    review = sub.add_parser("review")
    review.add_argument("--batch-id", required=True)
    review.add_argument("--sha256", required=True, help="The payload_sha256 verified in the review artifact")
    review.add_argument("--user", required=True)
    review.add_argument("--decision", choices=("approve", "reject"), required=True)
    review.add_argument("--allow-gate-exceptions", action="store_true")
    publish = sub.add_parser("publish")
    publish.add_argument("--batch-id", required=True)
    args = parser.parse_args()
    reviewer = None
    batch = None
    if args.command == "stage":
        try:
            batch = pub.ChangeBatch.model_validate_json(args.file.read_bytes())
        except Exception:
            raise SystemExit("invalid_batch_file") from None
    if args.command == "review":
        # Fail closed instead of getpass falling back to echoing a password.
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("Reviewer password: ")
        except (getpass.GetPassWarning, EOFError):
            raise SystemExit("secure_password_input_required") from None
        account = check_account(args.user, password)
        if not account or not account.reviewer:
            raise SystemExit("reviewer_authentication_required")
        reviewer = account.user
    con = db.connect_read_only() if args.command == "inspect" else db.connect()
    try:
        if args.command == "stage":
            result = pub.stage(con, batch)
        elif args.command == "inspect":
            result = pub.inspect(con, args.batch_id)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            # Never write drafts to stdout, and never overwrite another review artifact.
            descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(result, output, ensure_ascii=False, indent=2)
            result = {"batch_id": args.batch_id, "payload_sha256": result["payload_sha256"], "status": result["status"]}
        elif args.command == "review":
            result = pub.review(con, args.batch_id, args.sha256, reviewer, approve=args.decision == "approve",
                                allow_gate_exceptions=args.allow_gate_exceptions)
        else:
            result = pub.publish(con, args.batch_id)
        print(json.dumps(result, sort_keys=True))
    except pub.PublicationError as exc:
        raise SystemExit(exc.code) from None
    finally:
        con.close()


if __name__ == "__main__":
    main()

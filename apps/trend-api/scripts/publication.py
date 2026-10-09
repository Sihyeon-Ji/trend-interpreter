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
from trend_agents.storage import publication_inputs as inputs  # noqa: E402


def private_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(payload)


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
    export = sub.add_parser("export-translations")
    export.add_argument("--term-id", action="append", required=True)
    export.add_argument("--snapshot-id", required=True)
    export.add_argument("--snapshot-sha256", required=True)
    export.add_argument("--out", type=Path, required=True)
    pack = sub.add_parser("pack-translations")
    pack.add_argument("--input", type=Path, required=True)
    pack.add_argument("--results", type=Path, required=True)
    pack.add_argument("--run", type=Path, required=True)
    pack.add_argument("--batch-id", required=True)
    pack.add_argument("--out", type=Path, required=True)
    pack.add_argument("--skip-failed", action="store_true")
    pack.add_argument("--exclude-term", action="append", default=[], help="사람이 번역 검토에서 뺀 표제어 ID(여러 번)")
    args = parser.parse_args()
    if args.command == "pack-translations":
        try:
            batch, failures = inputs.pack_translations(args.input.read_bytes(), args.results.read_bytes(),
                                                       json.loads(args.run.read_bytes()), args.batch_id,
                                                       skip_failed=args.skip_failed, exclude=frozenset(args.exclude_term))
            private_write(args.out, pub.canonical(batch).encode())
        except pub.PublicationError as exc:
            raise SystemExit(exc.code) from None
        except Exception:
            raise SystemExit("invalid_translation_files_or_output") from None
        print(json.dumps({"batch_id": batch.batch_id, "payload_sha256": pub.digest(batch), "item_count": len(batch.items),
                          "skipped_failed_rows": failures, "excluded_by_review": len(set(args.exclude_term))}, sort_keys=True))
        return
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
    con = db.connect_read_only() if args.command in ("inspect", "export-translations") else db.connect()
    try:
        if args.command == "stage":
            result = pub.stage(con, batch)
        elif args.command == "export-translations":
            try:
                payload = inputs.translation_inputs(con, args.term_id, args.snapshot_id, args.snapshot_sha256)
                private_write(args.out, payload)
            except pub.PublicationError:
                raise
            except Exception:
                raise pub.PublicationError("invalid_translation_input_or_output") from None
            import hashlib
            result = {"item_count": len(args.term_id), "input_sha256": hashlib.sha256(payload).hexdigest()}
        elif args.command == "inspect":
            result = pub.inspect(con, args.batch_id)
            # Never write drafts to stdout, and never overwrite another review artifact.
            private_write(args.out, json.dumps(result, ensure_ascii=False, indent=2).encode())
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

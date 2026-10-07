"""Configure an existing dedicated publisher role as the prepared database owner."""
import argparse
import json

from trend_agents.storage import db, publisher_permissions
from trend_agents.storage.publications import PublicationError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    con = None
    try:
        con = db.connect_existing()
        print(json.dumps(publisher_permissions.configure(con, args.role), sort_keys=True))
    except PublicationError as exc:
        raise SystemExit(exc.code) from None
    except Exception:
        raise SystemExit("publisher_role_configuration_failed") from None
    finally:
        if con is not None:
            con.close()


if __name__ == "__main__":
    main()

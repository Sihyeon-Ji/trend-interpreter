"""Record a verified release without including secret values or request data."""

import argparse
import os
from pathlib import Path


def format_summary(
    service: str,
    previous: str,
    revision: str,
    image: str,
    secret: str,
    model: str,
    checks: str,
    commit: str,
) -> str:
    return (
        f"## {service} 배포 완료\n\n"
        f"| 항목 | 값 |\n| --- | --- |\n"
        f"| Commit | `{commit}` |\n"
        f"| 이전 revision | `{previous or '최초 배포'}` |\n"
        f"| 새 revision | `{revision}` |\n"
        f"| Image digest | `{image}` |\n"
        f"| Secret version | `{secret}` |\n"
        f"| Model | `{model or '해당 없음'}` |\n"
        f"| 완료 검사 | {checks} |\n\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("service", "previous", "revision", "image", "secret", "model", "checks"):
        parser.add_argument(f"--{name.replace('_', '-')}", required=True)
    args = parser.parse_args()
    summary = format_summary(
        args.service,
        args.previous,
        args.revision,
        args.image,
        args.secret,
        args.model,
        args.checks,
        os.getenv("GITHUB_SHA", "local-run"),
    )
    destination = os.getenv("GITHUB_STEP_SUMMARY")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as output:
            output.write(summary)
    else:
        print(summary, end="")


if __name__ == "__main__":
    main()

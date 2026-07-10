#!/usr/bin/env python3
"""Check active Canadian job URLs and mark definitively closed jobs inactive.

The checker is intentionally conservative:
- 404/410 responses are closed.
- Strong "job expired/filled/no longer available" page text is closed.
- 403, 429, 5xx, timeouts, DNS errors, and bot challenges are UNKNOWN and
  never deactivate a listing.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from canada_filter import is_canadian_listing


CLOSED_PHRASES = (
    "this job is no longer available",
    "this position is no longer available",
    "job is no longer available",
    "position is no longer available",
    "job posting is no longer available",
    "no longer accepting applications",
    "this job has expired",
    "this position has expired",
    "job posting has expired",
    "position has been filled",
    "this role has been filled",
    "requisition has been closed",
    "job requisition is closed",
    "applications are now closed",
    "the job you are looking for is no longer available",
)

CLOSED_PATH_MARKERS = (
    "job-not-found",
    "job_not_found",
    "job-expired",
    "job_expired",
    "position-closed",
    "position_closed",
)

BOT_OR_ACCESS_PHRASES = (
    "access denied",
    "verify you are human",
    "checking your browser",
    "enable javascript and cookies to continue",
    "captcha",
)

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CheckResult:
    url: str
    status: str  # open, closed, unknown
    reason: str
    http_status: int | None = None
    final_url: str | None = None


def normalize_page_text(body: bytes, charset: str | None) -> str:
    encoding = charset or "utf-8"
    try:
        text = body.decode(encoding, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    text = html.unescape(TAG_RE.sub(" ", text))
    return WHITESPACE_RE.sub(" ", text).casefold().strip()


def _closed_phrase(text: str) -> str | None:
    for phrase in CLOSED_PHRASES:
        if phrase in text:
            return phrase
    return None


def check_url(url: str, timeout: float, max_bytes: int) -> CheckResult:
    if not url or not urllib.parse.urlparse(url).scheme.startswith("http"):
        return CheckResult(url=url, status="unknown", reason="missing or unsupported URL")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; CanadaNewGradJobChecker/1.0; "
                "+https://github.com/SimplifyJobs/New-Grad-Positions)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.8",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )

    try:
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            status_code = getattr(response, "status", None) or response.getcode()
            final_url = response.geturl()
            body = response.read(max_bytes)
            text = normalize_page_text(body, response.headers.get_content_charset())

            final_path = urllib.parse.urlparse(final_url).path.casefold()
            if any(marker in final_path for marker in CLOSED_PATH_MARKERS):
                return CheckResult(
                    url=url,
                    status="closed",
                    reason=f"redirected to a closed-job path: {final_path}",
                    http_status=status_code,
                    final_url=final_url,
                )

            phrase = _closed_phrase(text)
            if phrase:
                return CheckResult(
                    url=url,
                    status="closed",
                    reason=f'page contains "{phrase}"',
                    http_status=status_code,
                    final_url=final_url,
                )

            if any(phrase in text for phrase in BOT_OR_ACCESS_PHRASES):
                return CheckResult(
                    url=url,
                    status="unknown",
                    reason="bot protection or access challenge",
                    http_status=status_code,
                    final_url=final_url,
                )

            if 200 <= status_code < 400:
                return CheckResult(
                    url=url,
                    status="open",
                    reason="page responded without a closed-job signal",
                    http_status=status_code,
                    final_url=final_url,
                )

            return CheckResult(
                url=url,
                status="unknown",
                reason=f"unexpected HTTP status {status_code}",
                http_status=status_code,
                final_url=final_url,
            )

    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return CheckResult(
                url=url,
                status="closed",
                reason=f"HTTP {exc.code}",
                http_status=exc.code,
                final_url=exc.geturl(),
            )
        return CheckResult(
            url=url,
            status="unknown",
            reason=f"HTTP {exc.code}; not safe to deactivate",
            http_status=exc.code,
            final_url=exc.geturl(),
        )
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as exc:
        return CheckResult(
            url=url,
            status="unknown",
            reason=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # Fail safe: never close on an unexpected checker bug.
        return CheckResult(
            url=url,
            status="unknown",
            reason=f"unexpected {type(exc).__name__}: {exc}",
        )


def write_step_summary(
    checked: int,
    closed: list[tuple[dict[str, Any], CheckResult]],
    open_count: int,
    unknown: list[tuple[dict[str, Any], CheckResult]],
) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = [
        "## Canada job link check",
        "",
        f"- Checked: **{checked}**",
        f"- Open: **{open_count}**",
        f"- Marked inactive: **{len(closed)}**",
        f"- Unknown/transient: **{len(unknown)}**",
        "",
    ]

    if closed:
        lines.extend(["### Marked inactive", ""])
        for listing, result in closed[:100]:
            lines.append(
                f"- **{listing.get('company_name', 'Unknown')} — "
                f"{listing.get('title', 'Unknown')}**: {result.reason}"
            )
        lines.append("")

    if unknown:
        lines.extend(["### Unknown (left active)", ""])
        for listing, result in unknown[:50]:
            lines.append(
                f"- **{listing.get('company_name', 'Unknown')} — "
                f"{listing.get('title', 'Unknown')}**: {result.reason}"
            )
        if len(unknown) > 50:
            lines.append(f"- …and {len(unknown) - 50} more in the uploaded JSON report.")
        lines.append("")

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--listings",
        default=".github/scripts/listings.json",
        help="Path to listings.json",
    )
    parser.add_argument(
        "--report",
        default="/tmp/canada-job-check-report.json",
        help="Path for the detailed check report",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-bytes", type=int, default=300_000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    listings_path = Path(args.listings)
    report_path = Path(args.report)

    try:
        listings = json.loads(listings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load {listings_path}: {exc}", file=sys.stderr)
        return 2

    candidates = [
        listing
        for listing in listings
        if listing.get("is_visible", True)
        and listing.get("active", False)
        and is_canadian_listing(listing)
        and isinstance(listing.get("url"), str)
        and listing["url"].strip()
    ]

    started_at = int(time.time())
    results_by_url: dict[str, CheckResult] = {}

    unique_urls = list(dict.fromkeys(listing["url"].strip() for listing in candidates))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_to_url = {
            executor.submit(check_url, url, args.timeout, args.max_bytes): url
            for url in unique_urls
        }
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results_by_url[url] = future.result()
            except Exception as exc:
                results_by_url[url] = CheckResult(
                    url=url,
                    status="unknown",
                    reason=f"worker failure: {type(exc).__name__}: {exc}",
                )

    now = int(time.time())
    closed: list[tuple[dict[str, Any], CheckResult]] = []
    unknown: list[tuple[dict[str, Any], CheckResult]] = []
    open_count = 0

    for listing in candidates:
        result = results_by_url[listing["url"].strip()]
        if result.status == "closed":
            closed.append((listing, result))
            if not args.dry_run:
                listing["active"] = False
                listing["date_updated"] = now
                listing["inactive_reason"] = f"Automated Canada link check: {result.reason}"
                listing["last_checked"] = now
        elif result.status == "open":
            open_count += 1
        else:
            unknown.append((listing, result))

    if closed and not args.dry_run:
        listings_path.write_text(json.dumps(listings, indent=4), encoding="utf-8")

    report = {
        "started_at": started_at,
        "finished_at": int(time.time()),
        "dry_run": args.dry_run,
        "checked_listings": len(candidates),
        "checked_unique_urls": len(unique_urls),
        "open": open_count,
        "closed": len(closed),
        "unknown": len(unknown),
        "results": [
            {
                "company_name": listing.get("company_name"),
                "title": listing.get("title"),
                **asdict(results_by_url[listing["url"].strip()]),
            }
            for listing in candidates
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    write_step_summary(len(candidates), closed, open_count, unknown)

    print(
        f"Checked {len(candidates)} Canadian listings: "
        f"{open_count} open, {len(closed)} closed, {len(unknown)} unknown."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

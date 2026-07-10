#!/usr/bin/env python3
"""Generate a Canada-only README from the upstream listings database."""

from datetime import datetime
import os

import util
from canada_filter import filter_canadian_listings


DEFAULT_EARLIEST_DATE = 1748761200  # Preserve the upstream project's cutoff.


def main() -> None:
    earliest_date = int(os.environ.get("EARLIEST_LISTING_DATE", DEFAULT_EARLIEST_DATE))

    listings = util.getListingsFromJSON()
    util.checkSchema(listings)

    filtered = util.filterListings(listings, earliest_date=earliest_date)
    filtered = filter_canadian_listings(filtered)

    # Preserve the upstream age-based stale logic, but do not render inactive
    # rows in the Canada-only README.
    filtered = util.mark_stale_listings(filtered)
    filtered = [listing for listing in filtered if listing.get("active", False)]

    util.sortListings(filtered)
    util.embedTable(filtered)

    util.setOutput("canadian_job_count", str(len(filtered)))
    util.setOutput(
        "commit_message",
        "Update Canadian new-grad jobs at "
        + datetime.now().strftime("%B %d, %Y %H:%M:%S"),
    )


if __name__ == "__main__":
    main()

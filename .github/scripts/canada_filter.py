#!/usr/bin/env python3
"""Location helpers for producing a Canada-only job list."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any


# These locations are distinctive enough to accept even when a province/country
# is omitted by the source. Ambiguous names such as London, Cambridge, Windsor,
# Hamilton, Richmond, Surrey, and Victoria intentionally are not included.
_DISTINCTIVE_CANADIAN_CITIES = {
    "toronto",
    "montreal",
    "calgary",
    "edmonton",
    "ottawa",
    "winnipeg",
    "saskatoon",
    "regina",
    "mississauga",
    "brampton",
    "markham",
    "vaughan",
    "guelph",
    "kitchener",
    "burnaby",
    "kelowna",
    "laval",
    "gatineau",
    "sherbrooke",
    "halifax",
    "moncton",
    "fredericton",
    "charlottetown",
    "st johns",
    "north york",
    "scarborough",
    "etobicoke",
    "kanata",
    "richmond hill",
    "waterloo",
    "vancouver",
}

_PROVINCES_AND_TERRITORIES = {
    "alberta",
    "british columbia",
    "manitoba",
    "new brunswick",
    "newfoundland and labrador",
    "newfoundland",
    "nova scotia",
    "northwest territories",
    "nunavut",
    "ontario",
    "prince edward island",
    "quebec",
    "saskatchewan",
    "yukon",
}

# Province abbreviations are matched in address-like positions only. This avoids
# treating the ordinary English word "on" as Ontario.
_PROVINCE_ABBREVIATION_RE = re.compile(
    r"(?:^|,\s*|\(\s*|-\s*)"
    r"(?:AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|PEI|QC|PQ|SK|YT)"
    r"(?:$|[\s,)/-])"
)

_EXPLICIT_NON_CANADA_RE = re.compile(
    r"\b(?:united states|u\.?s\.?a?\.?|united kingdom|u\.?k\.?|australia|india|germany|france)\b",
    re.IGNORECASE,
)


def _ascii_fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?:^|\b){re.escape(phrase)}(?:\b|$)", text) is not None


def is_canadian_location(location: str) -> bool:
    """Return True when a location clearly refers to Canada."""
    if not isinstance(location, str) or not location.strip():
        return False

    raw = location.strip()
    folded = _ascii_fold(raw)

    if _contains_phrase(folded, "canada") or _contains_phrase(folded, "canadian"):
        return True

    # Common ambiguous North American locations.
    if re.search(r"\bvancouver\s*,?\s*wa\b", folded):
        return False
    if re.search(r"\bontario\s*,?\s*ca\b", folded):
        return False

    if _EXPLICIT_NON_CANADA_RE.search(raw):
        return False

    if any(_contains_phrase(folded, province) for province in _PROVINCES_AND_TERRITORIES):
        return True

    if _PROVINCE_ABBREVIATION_RE.search(raw):
        return True

    return any(_contains_phrase(folded, city) for city in _DISTINCTIVE_CANADIAN_CITIES)


def _iter_locations(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        for item in value:
            if isinstance(item, str):
                yield item


def is_canadian_listing(listing: Mapping[str, Any]) -> bool:
    """Return True when at least one listing location is Canadian."""
    return any(is_canadian_location(location) for location in _iter_locations(listing.get("locations", [])))


def filter_canadian_listings(listings: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return listings that have at least one Canadian location."""
    return [listing for listing in listings if is_canadian_listing(listing)]

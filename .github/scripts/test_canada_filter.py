#!/usr/bin/env python3
import unittest

from canada_filter import (
    filter_canadian_listings,
    is_canadian_listing,
    is_canadian_location,
)


class CanadaFilterTests(unittest.TestCase):
    def test_country(self):
        self.assertTrue(is_canadian_location("Remote - Canada"))

    def test_province_abbreviation(self):
        self.assertTrue(is_canadian_location("Waterloo, ON"))

    def test_province_name(self):
        self.assertTrue(is_canadian_location("Halifax, Nova Scotia"))

    def test_city_only(self):
        self.assertTrue(is_canadian_location("Toronto"))

    def test_montreal_accent(self):
        self.assertTrue(is_canadian_location("Montréal"))

    def test_remote_without_country_is_not_canadian(self):
        self.assertFalse(is_canadian_location("Remote"))

    def test_us_location(self):
        self.assertFalse(is_canadian_location("New York, NY, United States"))

    def test_vancouver_washington(self):
        self.assertFalse(is_canadian_location("Vancouver, WA"))

    def test_ontario_california(self):
        self.assertFalse(is_canadian_location("Ontario, CA"))

    def test_listing_with_multiple_locations(self):
        listing = {"locations": ["Seattle, WA", "Toronto, ON"]}
        self.assertTrue(is_canadian_listing(listing))

    def test_filter(self):
        listings = [
            {"id": "ca", "locations": ["Ottawa, ON"]},
            {"id": "us", "locations": ["Boston, MA"]},
        ]
        self.assertEqual(
            [listing["id"] for listing in filter_canadian_listings(listings)],
            ["ca"],
        )


if __name__ == "__main__":
    unittest.main()

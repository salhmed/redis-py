import pytest

from redis.commands.search.query import GeoFilter
from redis.commands.search.querystring import (
    GeoValue,
    TagValue,
    between,
    geo,
    querystring,
)


class TestGeoHelper:
    """Unit tests for redis/commands/search/querystring.py:geo() bugfix.

    geo(lat, lon, ...) must return GeoValue(lon, lat, ...) so that
    the RediSearch string is "[lon lat radius unit]" (lon first).
    See redis/commands/search/query.py:GeoFilter(field, lon, lat, ...) for
    reference ordering.
    """

    def test_geo_basic_positional(self):
        # geo(lat=51.458, lon=-0.441) -> "[-0.441 51.458 10 km]"
        assert geo(51.458, -0.441, 10).to_string() == "[-0.441 51.458 10 km]"
        assert geo(51.458, -0.441, 10, unit="km").to_string() == "[-0.441 51.458 10 km]"

    def test_geo_basic_keywords(self):
        assert geo(lat=51.458, lon=-0.441, radius=10).to_string() == "[-0.441 51.458 10 km]"
        assert geo(lat=51.458, lon=-0.441, radius=10, unit="km").to_string() == "[-0.441 51.458 10 km]"
        # mixed kwargs
        assert geo(51.458, lon=-0.441, radius=10).to_string() == "[-0.441 51.458 10 km]"

    def test_geo_lon_lat_order_matches_geovalue(self):
        # GeoValue(lon, lat) is the canonical order
        assert geo(51.458, -0.441, 10).to_string() == GeoValue(-0.441, 51.458, 10).to_string()
        g = geo(13.361389, 38.115556, 100, unit="km")
        assert g.lon == 38.115556
        assert g.lat == 13.361389
        assert g.to_string() == "[38.115556 13.361389 100 km]"

    def test_geo_matches_geofilter_order(self):
        # GeoFilter(field, lon, lat, ...) uses lon first
        lon, lat, radius = -0.441, 51.458, 10
        gf = GeoFilter("loc", lon=lon, lat=lat, radius=radius, unit="km")
        # GeoFilter args are ["GEOFILTER", field, lon, lat, radius, unit]
        assert gf.args == ["GEOFILTER", "loc", lon, lat, radius, "km"]
        # querystring helper must produce same coordinate order inside brackets
        assert geo(lat, lon, radius).to_string() == f"[{lon} {lat} {radius} km]"

    def test_geo_units(self):
        assert geo(0, 0, 10, unit="km").to_string() == "[0 0 10 km]"
        assert geo(0, 0, 500, unit="m").to_string() == "[0 0 500 m]"
        assert geo(0, 0, 5, unit="mi").to_string() == "[0 0 5 mi]"
        assert geo(0, 0, 100, unit="ft").to_string() == "[0 0 100 ft]"

    def test_geo_negative_and_float_coords(self):
        assert geo(-33.865, 151.209, 5).to_string() == "[151.209 -33.865 5 km]"
        assert geo(40.7128, -74.0060, 10).to_string() == "[-74.006 40.7128 10 km]"
        # int coords
        assert geo(10, 20, 5).to_string() == "[20 10 5 km]"

    def test_geo_querystring_integration(self):
        # Single field
        assert querystring(loc=geo(51.458, -0.441, 10)) == "@loc:[-0.441 51.458 10 km]"
        # With custom unit
        assert querystring(loc=geo(51.458, -0.441, 100, unit="m")) == "@loc:[-0.441 51.458 100 m]"
        # Combined with other helpers
        q = querystring(loc=geo(51.458, -0.441, 10), name="bob")
        # Intersect node joins with space
        assert "@loc:[-0.441 51.458 10 km]" in q
        assert "@name:bob" in q

    def test_geo_distinct_lat_lon_caught(self):
        # This assertion failed before the fix (inversion bug)
        # It ensures lat/lon are NOT swapped
        g = geo(1, 2, 10)
        assert g.to_string() != "[1 2 10 km]", "lat/lon still inverted"
        assert g.to_string() == "[2 1 10 km]"

    def test_geovalue_direct(self):
        # GeoValue itself was always correct (lon, lat)
        assert GeoValue(-0.441, 51.458, 10).to_string() == "[-0.441 51.458 10 km]"
        assert GeoValue(20, 10, 5).to_string() == "[20 10 5 km]"

    def test_querystring_tags_and_between_still_work(self):
        # Sanity: other helpers unaffected
        assert between(1, 10).to_string() == "[1 10]"
        assert TagValue("a", "b").to_string() == "{a | b}"
        assert querystring(num=between(1, 10)) == "@num:[1 10]"

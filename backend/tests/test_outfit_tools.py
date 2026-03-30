import unittest

from services.outfit_react_agent import _extract_json_object
from services.outfit_tools import check_style_rules, pattern_compatible, weather_check


class OutfitToolsTests(unittest.TestCase):
    def test_pattern_compatible(self):
        self.assertTrue(pattern_compatible("solid", "floral"))
        self.assertFalse(pattern_compatible("stripes", "floral"))

    def test_check_style_rules(self):
        cand = {"formality": 3, "pattern": "solid"}
        items = [
            {"id": "a", "formality": 3, "pattern": "solid"},
            {"id": "b", "formality": 6, "pattern": "solid"},
        ]
        out = check_style_rules(cand, items)
        valid_ids = {x["id"] for x in out["valid_items"]}
        self.assertIn("a", valid_ids)
        self.assertNotIn("b", valid_ids)

    def test_weather_check(self):
        out = weather_check([{"id": "a", "type": "coat", "material": "wool"}], weather_temp=35, weather_conditions="rain")
        self.assertGreaterEqual(out["weather_score"], 0.6)

    def test_react_json_extract(self):
        raw = "here {\"tool\":\"FINAL\",\"tool_input\":{},\"final\":{\"selected_item_ids\":[\"1\"]}} there"
        obj = _extract_json_object(raw)
        self.assertIsInstance(obj, dict)
        self.assertEqual(obj.get("tool"), "FINAL")


if __name__ == "__main__":
    unittest.main()


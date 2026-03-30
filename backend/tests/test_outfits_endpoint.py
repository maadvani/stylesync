import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from config import settings
from main import app


class OutfitsEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("services.wardrobe_db.list_wardrobe_items")
    @patch("services.user_profile.get_color_season")
    @patch("services.trends_db.get_trends_for_user")
    def test_generate_outfits_rules(self, mock_trends, mock_season, mock_wardrobe):
        prev = settings.outfits_judge_enabled
        settings.outfits_judge_enabled = False
        try:
            mock_season.return_value = "deep_winter"
            mock_trends.return_value = []
            mock_wardrobe.return_value = [
                {"id": "w1", "type": "jeans", "primary_color": "black", "pattern": "solid", "formality": 3, "image_url": None},
                {"id": "w2", "type": "blazer", "primary_color": "navy", "pattern": "solid", "formality": 4, "image_url": None},
                {"id": "w3", "type": "shoes", "primary_color": "black", "pattern": "solid", "formality": 3, "image_url": None},
                {"id": "w4", "type": "skirt", "primary_color": "black", "pattern": "solid", "formality": 3, "image_url": None},
            ]

            payload = {
                "occasion": "work",
                "vibe": "modern",
                "weather_temp": 60,
                "weather_conditions": "clear",
                "engine": "rules",
                "candidate": {
                    "type": "top",
                    "primary_color": "white",
                    "pattern": "solid",
                    "formality": 3,
                    "seasons": ["spring", "fall"],
                },
            }
            r = self.client.post("/api/outfits/generate", json=payload)
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertIn("outfits", data)
            self.assertGreaterEqual(len(data["outfits"]), 1)
            self.assertEqual(data.get("debug", {}).get("engine"), "rules")
        finally:
            settings.outfits_judge_enabled = prev


if __name__ == "__main__":
    unittest.main()


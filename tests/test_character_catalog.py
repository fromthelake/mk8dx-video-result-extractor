import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mk8dx_video_result_extractor.data_paths import resolve_game_catalog_file
from mk8dx_video_result_extractor.game_catalog import load_game_catalog
from mk8dx_video_result_extractor.ocr_scoreboard_consensus import (
    describe_character_catalog_runtime,
    load_character_templates,
)


class CharacterCatalogTests(unittest.TestCase):
    def test_character_catalog_indices_are_contiguous_and_templates_exist(self):
        load_character_templates.cache_clear()
        catalog = load_game_catalog()
        indices = [character.character_index for character in catalog.characters]
        templates = load_character_templates()

        self.assertEqual(indices, list(range(82)))
        self.assertEqual(len(templates), 79)
        self.assertEqual(templates[0]["character_index"], 0)
        self.assertEqual(templates[0]["character_name"], "Mario")
        self.assertEqual(templates[-1]["character_index"], 78)
        self.assertEqual(templates[-1]["character_name"], "Pauline")

    def test_runtime_description_exposes_catalog_source_and_mapping_sample(self):
        description = describe_character_catalog_runtime()

        self.assertEqual(description["catalog_character_count"], 82)
        self.assertEqual(description["loaded_template_count"], 79)
        self.assertIn("game_catalog.json", description["catalog_path"])
        self.assertIn("0:Mario", description["first_mappings"])

    def test_game_catalog_resolves_from_packaged_fallback_when_checkout_file_is_absent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("mk8dx_video_result_extractor.data_paths.PROJECT_ROOT", Path(temp_dir)):
                catalog_path = resolve_game_catalog_file()

        self.assertTrue(str(catalog_path).replace("\\", "/").endswith("reference_data/game_catalog.json"))
        self.assertTrue(catalog_path.exists())


if __name__ == "__main__":
    unittest.main()

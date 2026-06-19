import json
import tempfile
import unittest
from pathlib import Path

from mk8dx_video_result_extractor.app_runtime import load_app_config
from mk8dx_video_result_extractor.project_paths import PROJECT_ROOT


class ConfigExampleTests(unittest.TestCase):
    def test_example_config_loads_when_local_config_is_absent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            temp_config_dir = temp_root / "config"
            temp_config_dir.mkdir()
            example_text = (PROJECT_ROOT / "config" / "app_config.example.json").read_text(encoding="utf-8")
            (temp_config_dir / "app_config.example.json").write_text(example_text, encoding="utf-8")

            config = load_app_config(base_dir=temp_root)

        self.assertEqual(config.export_image_format, "jpg")
        self.assertEqual(config.execution_mode, "cpu")
        self.assertEqual(config.easyocr_gpu_mode, "auto")
        self.assertFalse(config.write_debug_csv)

    def test_local_config_takes_precedence_over_example(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            temp_config_dir = temp_root / "config"
            temp_config_dir.mkdir()
            (temp_config_dir / "app_config.example.json").write_text(
                json.dumps({"export_image_format": "jpg"}),
                encoding="utf-8",
            )
            (temp_config_dir / "app_config.json").write_text(
                json.dumps({"export_image_format": "png"}),
                encoding="utf-8",
            )

            config = load_app_config(base_dir=temp_root)

        self.assertEqual(config.export_image_format, "png")


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from mk8dx_video_result_extractor.app_runtime import (
    AppConfig,
    detect_easyocr_runtime,
    easyocr_gpu_enabled,
)


def _config(easyocr_gpu_mode: str = "auto") -> AppConfig:
    return AppConfig(
        execution_mode="cpu",
        export_image_format="jpg",
        easyocr_gpu_mode=easyocr_gpu_mode,
        overlap_ocr_mode="auto",
        overlap_ocr_consumers=2,
        ocr_workers=16,
        score_analysis_workers=4,
        parallel_video_score_workers=2,
        pass1_scan_workers=2,
        ocr_consensus_frames=7,
        pass1_segment_overlap_frames=2100,
        pass1_min_segment_frames=27000,
        write_debug_csv=False,
        write_debug_score_images=False,
        write_debug_linking_excel=False,
        low_res_max_source_height=479,
        low_res_character_roi_pad_x=4,
        low_res_character_roi_pad_y=4,
        low_res_character_template_width=51,
        low_res_character_template_height=52,
        low_res_character_offset_x=4,
        low_res_character_offset_y=5,
        low_res_row12_character_fallback_min_confidence=75,
        low_res_row12_character_fallback_min_position_score=0.45,
        ultra_low_res_row_min_stddev=18.0,
        ultra_low_res_row_min_edge_density=0.035,
        ultra_low_res_blob_match_min_score=0.58,
        ultra_low_res_blob_match_min_margin=0.1,
    )


def _torch_runtime(cuda_available: bool) -> dict:
    return {
        "installed": True,
        "version": "2.10.0+cu128" if cuda_available else "2.11.0+cpu",
        "cuda_build": "12.8" if cuda_available else "",
        "cuda_available": cuda_available,
        "device_count": 1 if cuda_available else 0,
        "device_name": "NVIDIA Test GPU" if cuda_available else "",
        "reason": "test runtime",
    }


class EasyOcrRuntimeTests(unittest.TestCase):
    def test_auto_uses_cuda_when_torch_cuda_is_available(self):
        with patch("mk8dx_video_result_extractor.app_runtime.detect_torch_runtime", return_value=_torch_runtime(True)):
            runtime = detect_easyocr_runtime(_config("auto"))

        self.assertTrue(runtime["enabled"])
        self.assertEqual(runtime["backend"], "cuda")
        self.assertEqual(runtime["torch_cuda_build"], "12.8")
        self.assertIn("NVIDIA Test GPU", runtime["reason"])

    def test_auto_falls_back_to_cpu_for_cpu_only_torch(self):
        with patch("mk8dx_video_result_extractor.app_runtime.detect_torch_runtime", return_value=_torch_runtime(False)):
            runtime = detect_easyocr_runtime(_config("auto"))

        self.assertFalse(runtime["enabled"])
        self.assertEqual(runtime["backend"], "cpu")
        self.assertIn("CUDA was not available", runtime["reason"])

    def test_cpu_mode_disables_easyocr_gpu_even_when_torch_cuda_exists(self):
        with patch("mk8dx_video_result_extractor.app_runtime.detect_torch_runtime", return_value=_torch_runtime(True)):
            self.assertFalse(easyocr_gpu_enabled(_config("cpu")))
            runtime = detect_easyocr_runtime(_config("cpu"))

        self.assertFalse(runtime["enabled"])
        self.assertEqual(runtime["reason"], "CPU mode selected")


if __name__ == "__main__":
    unittest.main()

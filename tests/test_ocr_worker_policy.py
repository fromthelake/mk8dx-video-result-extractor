import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mk8dx_video_result_extractor.extract_text import current_ocr_worker_policy, easyocr_reader_lock_enabled


def _config(workers: int = 16):
    return SimpleNamespace(ocr_workers=workers)


class OcrWorkerPolicyTests(unittest.TestCase):
    def test_easyocr_gpu_uses_two_worker_default(self):
        with patch.dict("os.environ", {}, clear=True):
            policy = current_ocr_worker_policy(
                _config(16),
                easyocr_gpu=True,
                character_shortlist_acceleration=True,
            )

        self.assertEqual(policy["configured_workers"], 16)
        self.assertEqual(policy["effective_workers"], 2)
        self.assertEqual(policy["reason"], "easyocr_gpu_two_worker_default")

    def test_easyocr_gpu_default_respects_low_configured_worker_count(self):
        with patch.dict("os.environ", {}, clear=True):
            policy = current_ocr_worker_policy(
                _config(1),
                easyocr_gpu=True,
                character_shortlist_acceleration=True,
            )

        self.assertEqual(policy["configured_workers"], 1)
        self.assertEqual(policy["effective_workers"], 1)
        self.assertEqual(policy["reason"], "easyocr_gpu_two_worker_default")

    def test_easyocr_gpu_worker_override_is_experimental(self):
        with patch.dict("os.environ", {"MK8_GPU_OCR_WORKERS": "4"}, clear=False):
            policy = current_ocr_worker_policy(
                _config(16),
                easyocr_gpu=True,
                character_shortlist_acceleration=True,
            )

        self.assertEqual(policy["configured_workers"], 16)
        self.assertEqual(policy["effective_workers"], 4)
        self.assertEqual(policy["reason"], "easyocr_gpu_worker_override")

    def test_easyocr_cuda_worker_override_remains_compatible_alias(self):
        with patch.dict("os.environ", {"MK8_CUDA_OCR_WORKERS": "3"}, clear=False):
            policy = current_ocr_worker_policy(
                _config(16),
                easyocr_gpu=True,
                character_shortlist_acceleration=True,
            )

        self.assertEqual(policy["effective_workers"], 3)
        self.assertEqual(policy["reason"], "easyocr_gpu_worker_override")

    def test_cpu_with_character_prior_replay_uses_configured_workers(self):
        policy = current_ocr_worker_policy(
            _config(16),
            easyocr_gpu=False,
            character_shortlist_acceleration=True,
            character_prior_replay=True,
        )

        self.assertEqual(policy["configured_workers"], 16)
        self.assertEqual(policy["effective_workers"], 16)
        self.assertEqual(policy["reason"], "parallel_raw_ocr_deterministic_character_replay")

    def test_cpu_with_character_priors_without_replay_uses_single_worker(self):
        policy = current_ocr_worker_policy(
            _config(16),
            easyocr_gpu=False,
            character_shortlist_acceleration=True,
            character_prior_replay=False,
        )

        self.assertEqual(policy["configured_workers"], 16)
        self.assertEqual(policy["effective_workers"], 1)
        self.assertEqual(policy["reason"], "deterministic_character_prior_state")

    def test_cpu_without_character_priors_uses_configured_workers(self):
        policy = current_ocr_worker_policy(
            _config(16),
            easyocr_gpu=False,
            character_shortlist_acceleration=False,
            character_prior_replay=False,
        )

        self.assertEqual(policy["configured_workers"], 16)
        self.assertEqual(policy["effective_workers"], 16)
        self.assertEqual(policy["reason"], "configured_cpu_parallel")

    def test_easyocr_reader_lock_can_be_disabled_for_benchmarking(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(easyocr_reader_lock_enabled())
        with patch.dict("os.environ", {"MK8_DISABLE_EASYOCR_READER_LOCK": "1"}, clear=True):
            self.assertFalse(easyocr_reader_lock_enabled())


if __name__ == "__main__":
    unittest.main()

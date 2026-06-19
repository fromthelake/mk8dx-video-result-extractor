import unittest

from mk8dx_video_result_extractor.setup_torch import HardwareProfile, select_torch_package


def _profile(system: str, *gpu_names: str, nvidia_smi: bool = False) -> HardwareProfile:
    return HardwareProfile(
        system=system,
        machine="x86_64",
        gpu_names=tuple(gpu_names),
        nvidia_smi_available=nvidia_smi,
    )


class TorchPackageSelectionTests(unittest.TestCase):
    def test_windows_nvidia_auto_selects_cuda(self):
        decision = select_torch_package("auto", _profile("Windows", "NVIDIA RTX Test GPU"))

        self.assertEqual(decision.selected_mode, "cuda")
        self.assertTrue(decision.expected_gpu_ocr)
        self.assertFalse(decision.experimental)
        self.assertIn("cu128", decision.index_url)

    def test_windows_amd_auto_selects_cpu(self):
        decision = select_torch_package("auto", _profile("Windows", "AMD Radeon RX Test"))

        self.assertEqual(decision.selected_mode, "cpu")
        self.assertFalse(decision.expected_gpu_ocr)
        self.assertIn("ROCm is experimental", decision.reason)
        self.assertIn("torch==2.10.0+cpu", decision.pip_args)

    def test_windows_intel_auto_selects_cpu(self):
        decision = select_torch_package("auto", _profile("Windows", "Intel Arc Test"))

        self.assertEqual(decision.selected_mode, "cpu")
        self.assertFalse(decision.expected_gpu_ocr)

    def test_linux_nvidia_auto_selects_cuda_from_nvidia_smi(self):
        decision = select_torch_package("auto", _profile("Linux", nvidia_smi=True))

        self.assertEqual(decision.selected_mode, "cuda")
        self.assertTrue(decision.expected_gpu_ocr)

    def test_linux_amd_auto_selects_cpu(self):
        decision = select_torch_package("auto", _profile("Linux", "Advanced Micro Devices Radeon RX Test"))

        self.assertEqual(decision.selected_mode, "cpu")
        self.assertFalse(decision.expected_gpu_ocr)

    def test_macos_auto_selects_cpu(self):
        decision = select_torch_package("auto", _profile("Darwin", "Apple M3"))

        self.assertEqual(decision.selected_mode, "cpu")
        self.assertFalse(decision.expected_gpu_ocr)
        self.assertIn("MPS is experimental", decision.reason)

    def test_forced_cpu_always_selects_cpu(self):
        decision = select_torch_package("cpu", _profile("Windows", "NVIDIA RTX Test GPU"))

        self.assertEqual(decision.selected_mode, "cpu")
        self.assertFalse(decision.expected_gpu_ocr)

    def test_forced_cuda_warns_without_nvidia(self):
        decision = select_torch_package("cuda", _profile("Windows", "AMD Radeon RX Test"))

        self.assertEqual(decision.selected_mode, "cuda")
        self.assertTrue(decision.expected_gpu_ocr)
        self.assertTrue(any("NVIDIA hardware was not detected" in item for item in decision.warnings))
        self.assertIn("torch==2.10.0+cu128", decision.pip_args)

    def test_linux_rocm_experimental_is_opt_in(self):
        decision = select_torch_package("rocm-experimental", _profile("Linux", "AMD Radeon RX Test"))

        self.assertEqual(decision.selected_mode, "rocm-experimental")
        self.assertTrue(decision.expected_gpu_ocr)
        self.assertTrue(decision.experimental)
        self.assertIn("repo.radeon.com", decision.index_url)
        self.assertIn("-f", decision.pip_args)

    def test_windows_rocm_experimental_requires_manual_setup(self):
        decision = select_torch_package("rocm-experimental", _profile("Windows", "AMD Radeon RX Test"))

        self.assertEqual(decision.selected_mode, "rocm-experimental")
        self.assertTrue(decision.requires_manual_setup)
        self.assertFalse(decision.pip_args)

    def test_macos_mps_experimental_is_opt_in(self):
        decision = select_torch_package("mps-experimental", _profile("Darwin", "Apple M3"))

        self.assertEqual(decision.selected_mode, "mps-experimental")
        self.assertTrue(decision.expected_gpu_ocr)
        self.assertTrue(decision.experimental)
        self.assertIn("MK8_EASYOCR_GPU_MODE=gpu", decision.post_install_note)


if __name__ == "__main__":
    unittest.main()

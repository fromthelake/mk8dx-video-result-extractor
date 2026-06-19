# Linux and macOS Setup

Short setup guide for Linux and macOS.

GitHub:
- https://github.com/fromthelake/mk8dx-video-result-extractor

## Platform Status

- Linux: **UNKNOWN** in this stabilization pass. Setup is documented and should be verified on the target machine with `--check` and a scoped sample run.
- macOS: **UNKNOWN** in this stabilization pass. CPU OCR is the default path; CUDA is not available on Apple hardware.
- Windows 11 is the actively benchmarked and currently verified reference environment.
- iOS is not supported. This project depends on desktop Python, FFmpeg, OpenCV, EasyOCR, and local filesystem access.
- Linux NVIDIA GPU OCR is auto-selected when setup detects NVIDIA hardware.
- Linux AMD ROCm and macOS MPS are experimental opt-in paths, not verified support claims.
- After setup, always run `.venv/bin/mk8-local-play --check` and then a scoped sample run before trusting a new Linux/macOS environment.

## Important

For this project itself:
- everything runs from the local `.venv` inside this project folder
- do not install this app globally with `pip install ...`
- do not add `mk8-local-play` to your shell PATH
- always run the app from this project folder by using the local `.venv` command:
  - `.venv/bin/mk8-local-play`

System-wide installs are only for external tools such as:
- Git
- Python 3.12
- FFmpeg

Official resource pages:
- Git: https://git-scm.com/install/
- Python: https://www.python.org/downloads/ - install a Python `3.12.x` release, not Python 3.13 or newer
- FFmpeg: https://ffmpeg.org/download.html - package-manager installs are fine when they provide the `ffmpeg` command
- PyTorch: https://pytorch.org/get-started/locally/ - setup normally chooses and installs the correct PyTorch package for you

## Step 1. Choose where the project should live

Open a terminal in the parent folder where you want Git to create the project folder.

Examples:
- `~/Projects`
- `~/Documents`

Important:
- the `git clone` command in Step 4 will create a new folder named `mk8dx-video-result-extractor` inside the folder you opened

## Step 2. Check Git

Run:

Terminal Command:
--------------
git --version
--------------

If it works:
- continue to Step 3

If it fails:
- install Git with your system package manager or developer tools
- then run `git --version` again

Typical install commands:

Linux:
Terminal Command:
--------------
sudo apt-get update
sudo apt-get install git
--------------

macOS:
- run `git --version` and allow the Command Line Tools install if prompted

## Step 3. Check Python 3.12

Run:

Terminal Command:
--------------
python3.12 --version
--------------

If `python3.12 --version` shows Python 3.12:
- continue to Step 4

If Python is missing or not Python 3.12:
- install Python 3.12
- then open a new terminal and run `python3.12 --version` again

Typical install commands:

Linux:
Terminal Command:
--------------
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv python3-pip ffmpeg
--------------

macOS:
Terminal Command:
--------------
brew install python@3.12 ffmpeg
--------------

Important:
- this installs Python on your system
- the Mario Kart tool itself is still installed only inside this project folder's local `.venv`
- you do not need a global install of `mk8-local-play`

## Step 4. Download the project

Run:

Terminal Command:
--------------
git clone https://github.com/fromthelake/mk8dx-video-result-extractor.git
cd mk8dx-video-result-extractor
--------------

## Step 5. Run setup

Before setup, confirm FFmpeg is available:

Linux/macOS:
Terminal Command:
--------------
ffmpeg -version
--------------

Setup runs `--check`, and `--check` currently requires FFmpeg. If `ffmpeg -version` fails, install FFmpeg first and then rerun setup.

Run:

Terminal Command:
--------------
chmod +x ./scripts/setup_unix.sh
./scripts/setup_unix.sh
--------------

This setup script:
- creates or reuses the local `.venv` in this project folder
- creates `config/app_config.json` from `config/app_config.example.json` if the local config is absent
- uses `python3.12` by default and stops if the interpreter is not Python 3.12
- checks that FFmpeg is available before downloading Python packages
- scans local video-card hardware before choosing the PyTorch package set
- installs the app into that local `.venv`
- installs the Python OCR dependencies, including EasyOCR
- uses CUDA PyTorch automatically when NVIDIA hardware is detected on Linux
- uses CPU PyTorch for macOS, Intel, AMD default setup, no-GPU setup, or unclear hardware
- does not require a global install of this app
- does not require adding `mk8-local-play` to PATH

If setup succeeds:
- continue to Step 6

If setup fails:
- read the terminal error
- if the script reports the wrong Python version, delete `.venv`, set `PYTHON_BIN` to Python 3.12, and rerun it
- fix any other missing dependency
- run `./scripts/setup_unix.sh` again

## CPU And GPU Choices

Setup defaults to the fastest reliable package set it can identify. NVIDIA CUDA is the only plug-and-play GPU path this project currently recommends. CPU OCR remains the safe baseline on Linux and macOS:

Terminal Command:
--------------
.venv/bin/mk8-local-play --check
MK8_EASYOCR_GPU_MODE=cpu .venv/bin/mk8-local-play --check
--------------

Use CPU mode when:
- the machine has no NVIDIA GPU
- PyTorch reports a CPU-only build
- you are setting up macOS
- the machine has AMD or Intel graphics and you do not want to test experimental paths
- you want the most portable behavior first

Linux NVIDIA CUDA OCR is selected automatically when setup detects NVIDIA hardware. To force it manually:

Terminal Command:
--------------
TORCH_MODE=cuda ./scripts/setup_unix.sh
.venv/bin/mk8-local-play --check
--------------

What you want to see in `--check`:
- `PyTorch CUDA available: True`
- a real CUDA device name
- `EasyOCR mode: auto (ENABLED, backend=cuda, ...)`

If `--check` still reports CPU:
- confirm the NVIDIA driver is installed and visible with `nvidia-smi`
- confirm you installed PyTorch into this project's `.venv`, not into a global Python
- rerun `.venv/bin/python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"`
- leave `easyocr_gpu_mode` on `auto` or set `MK8_EASYOCR_GPU_MODE=gpu` only when you want a clear warning if CUDA is unavailable

Experimental AMD ROCm note:
- EasyOCR has no direct AMD/OpenCL equivalent to NVIDIA CUDA
- AMD may work when PyTorch ROCm exposes the GPU through the `torch.cuda` API
- this is Linux-only in the setup script and is not a verified support path
- it may fail to install, fail `--check`, run slower than CPU, or produce driver errors

Terminal Command:
--------------
TORCH_MODE=rocm-experimental ./scripts/setup_unix.sh
.venv/bin/mk8-local-play --check
--------------

What you want to see before trusting ROCm:
- `PyTorch HIP/ROCm build:` shows a version instead of `none`
- `PyTorch CUDA available: True`
- `EasyOCR mode: auto (ENABLED, backend=rocm, ...)`
- a small `--selection --video <file-name>` sample produces sensible output

If ROCm fails, rerun setup in CPU mode:

Terminal Command:
--------------
TORCH_MODE=cpu ./scripts/setup_unix.sh
--------------

Experimental macOS MPS note:
- CUDA is not available on Apple hardware
- EasyOCR can attempt MPS through PyTorch on some Macs
- this project has not verified or tuned MPS, so it is opt-in only

Terminal Command:
--------------
TORCH_MODE=mps-experimental ./scripts/setup_unix.sh
MK8_EASYOCR_GPU_MODE=gpu .venv/bin/mk8-local-play --check
--------------

What you want to see before trusting MPS:
- `PyTorch MPS available: True`
- `EasyOCR mode: gpu (ENABLED, backend=mps, ...)`
- a small sample run produces sensible output

If MPS fails, use CPU mode:

Terminal Command:
--------------
TORCH_MODE=cpu ./scripts/setup_unix.sh
--------------

OpenCV/extraction GPU note:
- the normal `opencv-python` package usually does not include OpenCV CUDA modules
- extraction is allowed to run on CPU and is the default tuned path
- CUDA/ROCm/MPS PyTorch mainly affects EasyOCR, not every OpenCV image operation

## Step 6. Run the environment check

Run:

Terminal Command:
--------------
.venv/bin/mk8-local-play --check
--------------

If the check succeeds:
- continue to Step 7

If the check succeeds, the project is ready to run entirely from:
- `.venv/bin/mk8-local-play`

## Step 7. Add your videos

Put your video files in folder:

`./Input_Videos/`

Optional:
- you can also place videos inside subfolders under `./Input_Videos/`
- use `--subfolders` if you want headless runs to include those subfolders

## Step 8. Run the tool

Process everything in `Input_Videos`:

Terminal Command:
--------------
.venv/bin/mk8-local-play --all
--------------

Process everything in `Input_Videos` and all subfolders:

Terminal Command:
--------------
.venv/bin/mk8-local-play --all --subfolders
--------------

Process only the current selected input set, including subfolders:

Terminal Command:
--------------
.venv/bin/mk8-local-play --selection --subfolders
--------------

Process a specific multi-video set by explicit relative file path:

Terminal Command:
-------------
.venv/bin/mk8-local-play --selection --subfolders --videos "2026-03-28/Kwalificatie_Groep_1_2026-03-27 20-00-33.mkv" "2026-03-28/Kwalificatie_Groep_2_2026-03-27 20-00-33.mp4"
-------------

When `--subfolders` is used:
- supported videos are discovered recursively under `./Input_Videos/`
- exported frame bundles and Excel/CSV `Video` names include a sanitized relative folder path
- this avoids naming conflicts when different folders contain files with the same base filename
- with `--videos`, explicit relative paths are matched exactly before filename fallback is attempted
- with `--videos`, folder entries are also valid (for example `"2026-03-28"`), and include all supported files inside that folder scope

Process only the current selected input set:

Terminal Command:
--------------
.venv/bin/mk8-local-play --selection
--------------

## Output

Results are written to folder:

`./Output_Results/`

## Commands

Open the GUI interface:

Terminal Command:
--------------
.venv/bin/mk8-local-play
--------------

What it does:
- starts the desktop GUI
- from the GUI you can:
  - open the input folder
  - merge videos
  - run extraction only
  - run a scoped selection pass
  - toggle subfolder-aware processing
  - run OCR/export only
  - open the latest Excel output
  - clear extracted races or output results

GUI command mapping:
- `Find Races In Videos`
  - finds and saves the race screens from your videos
- `Run Selected Videos`
  - does both steps in one go, but only for the selected videos
- `Also Look In Subfolders`
  - includes videos stored in folders inside `Input_Videos`
- `Create Excel Results`
  - reads the saved race screens and creates the Excel file

Run everything:

Terminal Command:
--------------
.venv/bin/mk8-local-play --all
--------------

What it does:
- runs extraction on all videos currently present in `Input_Videos`
- then runs OCR/export on all frames present in `Output_Results/Frames`

What it includes:
- the current videos in `Input_Videos`
- existing extracted frames already present in `Output_Results/Frames`

What it does not do:
- it does not limit OCR to only newly extracted frames

Add subfolders to `--all`:

Terminal Command:
--------------
.venv/bin/mk8-local-play --all --subfolders
--------------

What it changes:
- extraction also includes supported `.mp4`, `.mkv`, `.mov`, `.avi`, and `.webm` files found in subfolders under `Input_Videos`
- OCR/export still behaves like `--all`, so existing historical frame groups can still be included

Run only the current selected input set:

Terminal Command:
--------------
.venv/bin/mk8-local-play --selection
--------------

What it does:
- runs extraction on the currently selected videos in `Input_Videos`
- then runs OCR/export only for those same video classes

What it includes:
- only the selected/current input videos for this run
- only OCR groups that belong to those selected videos

What it does not do:
- it does not sweep unrelated historical frame groups from older videos

Add subfolders to `--selection`:

Terminal Command:
--------------
.venv/bin/mk8-local-play --selection --subfolders
--------------

What it changes:
- extraction includes the current selected input set across `Input_Videos` and its subfolders
- OCR/export stays scoped to only those subfolder-aware video classes

Run extraction only:

Terminal Command:
--------------
.venv/bin/mk8-local-play --extract
--------------

What it does:
- scans videos and exports frame bundles into `Output_Results/Frames`
- does not run OCR or create the final workbook

Run OCR/export only:

Terminal Command:
--------------
.venv/bin/mk8-local-play --ocr
--------------

What it does:
- runs OCR on the extracted frames currently present in `Output_Results/Frames`
- writes the workbook output

What it does not do:
- it does not extract frames from videos first

Run one video only with scoped OCR:

Terminal Command:
--------------
.venv/bin/mk8-local-play --selection --video Demo_CaptureCard_Race.mp4
--------------

What it does:
- extracts only that one video
- limits OCR/export to that same video class

Recommended use:
- use this when you want a true one-video run
- prefer this over `--all --video ...`, because `--all` can still include older frame groups during OCR

Run several exact videos together with scoped OCR:

Terminal Command:
-------------
.venv/bin/mk8-local-play --selection --subfolders --videos "2026-03-28/Kampioen_2026-03-27 21-50-56.mp4" "2026-03-28/Talent_2026-03-27 21-50-56.mp4" "2026-03-28/Wild_2026-03-27 21-50-56.mp4"
-------------

## Troubleshooting

First try these checks:

Terminal Command:
--------------
git --version
python3.12 --version
.venv/bin/mk8-local-play --check
--------------

Then read:
- [README.md](../README.md)
- [TECHNICAL_PIPELINE.md](./TECHNICAL_PIPELINE.md)



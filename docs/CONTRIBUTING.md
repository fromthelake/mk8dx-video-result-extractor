# Contributing

This project is aimed at practical hobby use, so contributions should optimize for:
- understandable behavior
- stable outputs
- cross-platform use
- changes that can be verified locally

## Development Rules

Prefer these priorities in order:

1. keep the pipeline correct
2. keep the code understandable
3. keep the repo easy to run from a fresh clone
4. optimize performance after correctness stays stable

## Naming And Comments

Use names that describe what the code does.

Good:
- `extract_initial_scan.py`
- `ocr_session_validation.py`
- `build_consensus_observation`

Avoid:
- vague internal labels like `pass1`, `pass2`, `misc`, `helper2`

Comments should explain:
- why a step exists
- what assumption it depends on
- what tradeoff is being made

Comments should not just restate the line below them.

## Cross-Platform Expectations

Changes should keep the repo usable on:
- Windows
- Linux
- macOS

That means:
- prefer `pathlib` or careful path handling
- do not hardcode Windows-only paths
- keep GUI optional
- keep CLI usable without GUI dependencies

## How To Test A Change

Minimum checks:

```bash
python -m compileall mk8dx_video_result_extractor
python -m unittest discover
python -m mk8dx_video_result_extractor.main --check
```

From a repo-local virtual environment, prefer the wrapper scripts:
- Windows: `.\scripts\run_tests.ps1`
- Linux/macOS: `./scripts/run_tests.sh`

Useful functional checks:

```bash
python -m mk8dx_video_result_extractor.main --extract --video Demo_CaptureCard_Race.mp4
python -m mk8dx_video_result_extractor.main --ocr --video Demo_CaptureCard_Race.mp4
```

If you change output logic, also compare against a baseline:

```bash
python tools/validate_outputs.py --baseline-dir <baseline-dir>
```

## Runtime Output Policy

Keep runtime output out of Git unless it is intentionally curated.

Normal runtime data belongs in:
- `Output_Results/`

Curated benchmark or regression material should be stored outside this runtime-focused repository.

## Performance Work

When changing performance-sensitive code:
- keep a baseline
- keep behavior stable
- note whether the change affects:
  - extraction speed
  - OCR quality
  - row mapping
  - total-score validation

## Documentation

If you change workflow, setup, commands, config, or repo structure, update:
- `README.md`
- `docs/PROJECT_STRUCTURE.md`
- `docs/CHANGELOG.md`

The repo should stay understandable for:
- a hobbyist user
- a junior developer
- a future maintainer coming back after months away

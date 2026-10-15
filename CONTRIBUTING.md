# Contributing to xFACE

Bug reports, feature ideas, documentation improvements and pull requests are all welcome.

## Reporting Bugs

- Search the existing [issues](https://github.com/KOKUTBON/xFACE/issues) first.
- Open a new issue with reproduction steps, expected vs. actual behavior, and your environment (OS, Python version, camera type, CompreFace version).
- **Never attach real face images, access logs or `.env` files** to an issue. Redact URLs and keys.

## Suggesting Enhancements

Open an issue describing the use case and the proposed behavior. Ideas that fit well: MQTT/Zigbee relays, liveness / anti-spoofing detection, multi-camera support, other recognition backends.

## Development Setup

```bash
git clone https://github.com/KOKUTBON/xFACE.git
cd xFACE
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

You can develop without a physical camera by pointing `CAMERA_INDEX` at a video file.

## Before Opening a Pull Request

```bash
ruff check .
pytest
```

- Tests run against a temporary database and data directory, so they never touch your local `data/`.
- Add tests under `tests/` for new behavior.
- Keep commits focused and use the imperative mood (`Add MQTT relay backend`).

## Development Guidelines

- **Thread safety**: camera access goes through `CameraService` and its re-entrant lock. Never join a thread while holding a lock it needs.
- **Paths**: validate any user-influenced path with `validate_path_within_directory()`.
- **Background independence**: recognition runs in `RecognitionWorker`; it must never depend on an open browser.
- **Frontend**: escape user-controlled strings with `escapeHtml()` before inserting them into HTML.
- **Privacy**: do not add telemetry or any feature that sends face data outside the user's own infrastructure.

## Community participation

Follow the [communication guidelines](COMMUNICATION.md) and [organizational governance](GOVERNANCE.md). Keep security and conduct reports confidential and use a verified private channel; never include sensitive details in a public issue. Maintainers verify the reporting contacts and channels listed in the [readiness checklist](RELEASE_CHECKLIST.md).

## KOKUTBON contribution principles

Contribute under the existing **MIT** license in [LICENSE](LICENSE). You retain copyright in your work. Submit only work you are entitled to share, identify third-party sources and preserve their notices. No copyright assignment or paid membership is required.

Open an issue for substantial proposals, then submit a focused pull request from a branch or fork. Describe the problem, implementation, relevant checks and any privacy, accessibility, migration or safety impact. Use synthetic fixtures and sanitized logs. Maintainer review and passing relevant CI checks are expected before merging. A sole maintainer may merge their own change after checks pass and must record the rationale; no fictitious second reviewer is required.

Small documentation, translation, accessibility and reproducibility improvements are welcome. Funding does not determine review priority. Follow [communication guidelines](COMMUNICATION.md) and [the sponsorship policy](SPONSORSHIP.md).

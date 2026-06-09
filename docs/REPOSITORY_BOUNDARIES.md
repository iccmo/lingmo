# Repository Boundaries

This repository should keep source code, tests, documentation, and small fixtures under version control.

Do not commit local runtime state or generated artifacts:

- `data/`: SQLite databases, platform auth JSON, publish screenshots, TTS cache, local backups.
- `frontend/dist/`: Vite production build output.
- `frontend/test-results/`, `test-results/`, `playwright-report/`: browser test output.
- `douyin-video/audio/`, `douyin-video/images/`, `douyin-video/output/`, `douyin-video/temp/`: generated media pipeline assets.
- `.coverage`, `.pytest_cache/`, `__pycache__/`, `node_modules/`, `.venv/`.

Use `.env.example` for configuration shape. Keep real `.env` files and provider keys local.

Docker builds generate `frontend/dist` inside the image and create runtime `data/` on first start, so a clean checkout should not need committed build output or databases.

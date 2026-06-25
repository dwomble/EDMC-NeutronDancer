# Neutron Dancer Agent Guide

## Commands & Workflow

### Build / Release Pack
```bash
zip -r EDMC-NeutronDancer.zip . \
    -x ".git/*" ".github/*" ".DS_Store" ".gitignore" \
      ".python-version" ".editorconfig" ".isort.cfg" "requirements*.txt" \
      "history/*" "tests/*" | gunzip > EDMC-NeutronDancer.zip.gz  # for VT scan, then unzip to artifact
```

## Testing & Lint Order (`lint -> test`)

Run full CI-equivalent lints and unit tests:

```bash
# lint first (flake8 only)
xvfb-run flake8 . --extend-exclude .venv,utils \
    --count --select=E9,F63,F7,F82 --show-source --statistics || echo "Fix these"

# then pytest with xvfb for headless rendering tests
xvfb-run pytest -m "not manual_only" --tb=short
```

**Note:** `pytest.ini` excludes `-m manual_only` marks by default. Use `-k` or remove marker to run those suites separately when troubleshooting flakiness from external dependencies.

## Test Suites & Prerequisites

- **Normal tests**: headless fixtures via xvfb, no special service deps
- **manual\_only** markers: long-running / network-dependent; verify env has access before enabling in pytest options
- Use `tests/journal_config/` or `tests/config/*.json` for test journal event files when writing scenarios

## Architecture Highlights

This is an **EDMC plugin**, not a standalone app. Code paths via EDMC's Python 2 compatibility shim:

- Entry point lives at `<plugin_folder>/load.py`, registered with EDMC as the module name string
- Journal events (`<system>.json`) drive state updates in `journal_entry()` handler
- Dashboard UI built on `tk` / custom notebook; overlay frame toggled after ~5s
- Clipboard: tries system tools first (wl-copy, xsel), falls back to Tk if none available

**Linux setup**: set `$EDMC_CLIPBOARD_CLI` before launching EDMC if needed. Flatpak users must ensure the CLI command is accessible from sandbox and can follow symlinks.

## Monorepo / Boundary Notes

Monolithic plugin structure:
- `Router/*`: core routing & carrier state machine
- `<plugin_folder>/load.py` + journal hooks integrate with main EDMC process via EDMDMarketConnector's Python event loop (not the connector itself)

Do not assume any code in this repo is meant to run as a standalone script outside plugin context.

## Release Workflow (on github.com/dwomble/EDMC-NeutronDancer)

Pushing a tag triggers release:
1. CI writes new version number into `version` file from git ref → commits/pushes update back to master automatically
2. Releases zip excludes tests/history/config files and runs VirusTotal scan on artifact before publishing
3. Manual steps for custom releases only; this workflow assumes automatic post-release flow

**If adding a PR branch release path**: you'll need `push:branches:[<branch>]` added alongside current `release.published` trigger; also add `.ciignore` if releasing artifacts from forks with sensitive envs (e.g., upload to S3).
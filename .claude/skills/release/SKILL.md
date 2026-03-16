---
name: release
description: Publish a new claude-storm release. Bumps the version, runs checks, commits, creates a git tag, then hands off push + GitHub Release creation to the user.
argument-hint: "[version]"
---

# Release

## Phase 0 — Determine version

Parse `$ARGUMENTS` for an explicit version string (e.g. `0.4.0`).

If no version was provided:
1. Read `pyproject.toml` to find the current version
2. Report the current version to the user
3. Ask what the new version should be (semver: `MAJOR.MINOR.PATCH`)

Wait for confirmation before proceeding.

## Phase 1 — Pre-flight checks

Run the following in order. **Stop and report if either fails** — do not proceed to Phase 2.

1. `uv run ruff check .` — lint
2. `uv run ruff format --check .` — format check
3. `uv run pytest` — test suite

If all pass, report "All checks passed" and continue.

## Phase 2 — Bump version

Edit `pyproject.toml`: update the `version` field to the new version.

Do not change anything else.

## Phase 3 — Commit and tag

1. Stage `pyproject.toml`:
   ```
   git add pyproject.toml
   ```
2. Commit:
   ```
   git commit -m "chore: bump version to X.Y.Z"
   ```
3. Create an annotated tag:
   ```
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   ```

## Phase 4 — Hand off to user

Print the following block **verbatim** (substituting the actual version):

---
**Claude's steps are done. Your turn:**

Run these commands in order:

```bash
git push origin main
git push origin vX.Y.Z
```

Then go to GitHub and create the release:
1. Open https://github.com/phobologic/claude_storm/releases/new
2. Select tag `vX.Y.Z`
3. Set the title to `vX.Y.Z`
4. Add release notes (what changed in this version)
5. Click **Publish release**

Publishing the release triggers the `publish.yml` workflow, which builds the package and pushes it to PyPI automatically.
---

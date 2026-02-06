#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only act on Python files
if [[ -z "$FILE_PATH" || ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

# Fix lint issues, then format
uv run ruff check --fix "$FILE_PATH" 2>&1
uv run ruff format "$FILE_PATH" 2>&1

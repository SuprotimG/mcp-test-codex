#!/usr/bin/env bash
set -euo pipefail

ROLE="${1:-${SOFTWARE_FACTORY_ROLE:-}}"

if [[ -z "${ROLE}" ]]; then
  echo "Usage: ./scripts/sandcastle/run-role.sh <planner|developer|reviewer|merger>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"
export SOFTWARE_FACTORY_ROLE="${ROLE}"

exec npx --yes --package @ai-hero/sandcastle@latest --package tsx@latest tsx .sandcastle/main.ts "${ROLE}"


#!/usr/bin/env bash
# Run repository unit tests.

set -euo pipefail

printf "\n[run-tests] Discovering tests under ./tests\n"
python -m unittest discover -s tests -p "test_*.py"

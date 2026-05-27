#!/usr/bin/env bash

# Runs the pi command 100 times in a row.
# Usage: ./practice.sh

if ! command -v pi >/dev/null 2>&1; then
  echo "What is reality? look at pi.dev and return back"
  exit 1
fi

echo "What is reality?"
for i in {1..100}; do
  ./sit.sh
  echo "mu!..."
  # Optionally stop if the command fails:
  # if [ $? -ne 0 ]; then exit 1; fi
done

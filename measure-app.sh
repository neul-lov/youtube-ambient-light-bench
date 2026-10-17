#!/bin/zsh
# Measure an app that is already running for a while, e.g. the YouTube web app from the Dock,
# once with the userscript and once without, and compare the two rows.
#   ./measure-app.sh LABEL [SECONDS] [APP_REGEX]
# APP_REGEX matches the command line of the app responsible for the processes
# (default: any Safari web app; use e.g. "YouTube.app" for one, or "Safari.app" for Safari).
set -e
cd "${0:A:h}"
label=${1:?usage: ./measure-app.sh LABEL [SECONDS] [APP_REGEX]}
secs=${2:-30}
app=${3:-"Web App.app/Contents/MacOS/Web App"}

run=results/$(date +%Y%m%d-%H%M%S)-app-${label//[^A-Za-z0-9._-]/-}
mkdir -p $run
python3 tools/sampler.py $run/samples.jsonl & smp=$!
trap 'kill $smp 2>/dev/null' EXIT INT TERM
sleep $((secs + 2))
kill $smp; wait $smp 2>/dev/null || true
python3 tools/analyze.py $run --whole "$label" --app "$app" | tee $run/summary.txt

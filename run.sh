#!/bin/zsh
# Run a benchmark in Safari and print the per-phase table (also saved to results/<run>/summary.txt).
#   ./run.sh pipeline [upload|schedule|crossfade]
#   ./run.sh userscript A.user.js B.user.js
# EXTRA adds URL parameters, e.g. EXTRA="sec=5&warm=1" ./run.sh pipeline schedule for a quick run.
set -e
cd "${0:A:h}"
PORT=${PORT:-8767}
usage="usage: ./run.sh pipeline [upload|schedule|crossfade] | ./run.sh userscript A.user.js B.user.js"

case $1 in
  pipeline)
    suite=${2:-upload}
    url="http://127.0.0.1:$PORT/pipeline/?suite=$suite${EXTRA:+&$EXTRA}"
    name="pipeline-$suite" ;;
  userscript)
    [[ -f $2 && -f $3 ]] || { echo $usage; exit 1; }
    mkdir -p userscript-ab/scripts
    cp "$2" userscript-ab/scripts/a.js
    cp "$3" userscript-ab/scripts/b.js
    url="http://127.0.0.1:$PORT/userscript-ab/${EXTRA:+?$EXTRA}"
    name=userscript-ab ;;
  *) echo $usage; exit 1 ;;
esac

[[ -f media/test-4k60.mp4 ]] || ./make-video.sh

run=results/$(date +%Y%m%d-%H%M%S)-$name
mkdir -p $run
python3 tools/server.py $PORT $run/events.jsonl & srv=$!
python3 tools/sampler.py $run/samples.jsonl & smp=$!
trap 'kill $srv $smp 2>/dev/null' EXIT INT TERM
sleep 1

echo "Running $name in Safari. Keep the Safari window visible until it finishes. Results: $run"
open -g -a Safari "$url"
until grep -q '"ev": "done"' $run/events.jsonl 2>/dev/null; do sleep 2; done
kill $smp; wait $smp 2>/dev/null || true
python3 tools/analyze.py $run | tee $run/summary.txt

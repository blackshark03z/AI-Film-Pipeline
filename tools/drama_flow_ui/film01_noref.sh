# Text-only film01 generations, one at a time. A generation counts as passed
# only if a <video> can be downloaded from the newest tile AND that download
# differs from the newest tile before sending (else STALE_TILE).
# Run from the repo root: bash tools/drama_flow_ui/film01_noref.sh SC01_g1 ...
HERE="$(cd "$(dirname "$0")" && pwd)"
PR="docs/drama/film01_prompts/noref"
OUT="docs/drama/film01_takes/noref"
mkdir -p "$OUT"
for g in "$@"; do
  python -W ignore "$HERE/flow_tab.py" key Escape >/dev/null
  # sha256 of the newest tile before this send
  pre=$(python -W ignore "$HERE/flow_dl2.py" 493 215 "$OUT/.pre_$g.mp4")
  rm -f "$OUT/.pre_$g.mp4"
  case "$pre" in *saved*) prev=${pre##* };; *) prev="";; esac
  python -W ignore "$HERE/flow_tab.py" type "$(cat "$PR/$g.txt")" >/dev/null || { echo "$g SEND_FAILED"; continue; }
  t0=$(date +%s); sleep 15
  for i in $(seq 1 40); do
    p=$(python -W ignore "$HERE/flow_tab.py" js "/NORA: Black/.test(document.body.innerText)" | tr -d '"')
    [ "$p" = false ] && break; sleep 10
  done
  sleep 5
  r=$(python -W ignore "$HERE/flow_dl2.py" 493 215 "$OUT/$g.mp4")
  case "$r" in
    *saved*)
      sha=${r##* }
      if [ -n "$prev" ] && [ "$sha" = "$prev" ]; then
        echo "$g STALE_TILE $(( $(date +%s)-t0 ))s"
      else
        echo "$g PASSED $(( $(date +%s)-t0 ))s $sha"
      fi;;
    *) echo "$g BLOCKED $(( $(date +%s)-t0 ))s";;
  esac
  python -W ignore "$HERE/flow_tab.py" shot "noref_$g.png" >/dev/null
done
echo BATCH_DONE

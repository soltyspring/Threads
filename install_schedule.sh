#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
project_dir="$PWD"
if [[ "$project_dir" == *' '* || "$project_dir" == *'%'* ]]; then
  echo 'Install in a path without spaces or percent signs.' >&2
  exit 1
fi
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p runtime
chmod 700 runtime
if [[ -f .env ]]; then chmod 600 .env; fi
.venv/bin/python threads_schedule.py check
.venv/bin/python threads_schedule.py init
cron_tmp="$(mktemp)"
trap 'rm -f -- "$cron_tmp"' EXIT
if crontab -l > "$cron_tmp" 2> runtime/crontab_read_error.log; then
  cp -- "$cron_tmp" runtime/crontab_before.txt
elif grep -q 'no crontab for' runtime/crontab_read_error.log; then
  : > "$cron_tmp"
else
  echo 'Unable to read existing crontab; it was not modified.' >&2
  exit 1
fi
if grep -q '# threds-cute-week' "$cron_tmp"; then
  echo 'Existing campaign cron entry found; refusing to duplicate.' >&2
  exit 1
fi
printf '\n* * * * * cd %s && %s/.venv/bin/python threads_schedule.py run >> %s/runtime/scheduler.log 2>&1 # threds-cute-week\n' "$project_dir" "$project_dir" "$project_dir" >> "$cron_tmp"
crontab "$cron_tmp"
.venv/bin/python threads_schedule.py status
echo 'Installed finite 84-post queue. No posts are sent by this installer.'

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
backup_dir="${1:-./backups}"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
umask 077
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
compose=(docker compose -f compose.yaml -f compose.production.yaml)
# Briefly stop writers so the database and media archive describe the same point.
"${compose[@]}" stop api worker
trap '"${compose[@]}" start api worker' EXIT
"${compose[@]}" exec -T db pg_dump -U founderos -d founderos -Fc > "$backup_dir/$stamp.database.dump"
"${compose[@]}" run --rm --no-deps --entrypoint tar api -czf - -C /app/media . > "$backup_dir/$stamp.media.tar.gz"
printf 'Backup saved in %s\n' "$backup_dir"

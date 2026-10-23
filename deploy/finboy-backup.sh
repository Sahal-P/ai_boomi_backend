#!/bin/sh
set -eu
umask 077
install -d -m 700 /var/backups/finboy
snapshot="/var/backups/finboy/$(date -u +%Y%m%dT%H%M%SZ).dump"
runuser -u postgres -- pg_dump --format=custom --dbname=finboy_prod > "$snapshot.partial"
pg_restore --list "$snapshot.partial" > /dev/null
mv "$snapshot.partial" "$snapshot"
find /var/backups/finboy -name '*.dump' -type f -mtime +6 -delete

#!/bin/sh
# Docker entrypoint for the DMS backend.
#
# Schema migrations (DDL) require the MySQL root account. The container is only
# given MIGRATION_DB_USER / MIGRATION_DB_PASSWORD (the root password) for this
# single purpose: running `alembic upgrade head` on boot. Immediately after the
# migrations complete they are unset from this shell's environment, so the
# long-running uvicorn process launched below never holds the MySQL root
# password (it is absent from memory and from /proc/<pid>/environ).
#
# When no migration credentials are provided the script skips schema work and
# starts the app directly (e.g. local development, where the app runs Alembic
# itself using MIGRATION_DB_PASSWORD from backend/.env).

set -e

if [ -n "${MIGRATION_DB_PASSWORD}" ]; then
    echo "Running database schema migrations as '${MIGRATION_DB_USER:-root}'..."

    _attempts=10
    _delay=3
    _n=0
    while :; do
        _n=$((_n + 1))
        if alembic upgrade head; then
            break
        fi
        if [ "$_n" -ge "$_attempts" ]; then
            echo "Database migrations failed after ${_attempts} attempts." >&2
            exit 1
        fi
        echo "Migrations attempt ${_n}/${_attempts} failed; retrying in ${_delay}s..." >&2
        sleep "$_delay"
    done

    # The privileged migration credentials have served their only purpose.
    unset MIGRATION_DB_PASSWORD MIGRATION_DB_USER
    echo "Schema migrations complete; migration credentials removed from the process environment."
fi

exec "$@"
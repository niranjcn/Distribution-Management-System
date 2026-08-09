#!/bin/bash
# Least-privilege grants for the application user.
#
# Runs only on the first MySQL initialization (docker-entrypoint-initdb.d).
# Credentials come from the container environment (MYSQL_ROOT_PASSWORD,
# MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE) - never hardcode secrets here.
#
# The runtime user gets only the DML privileges the application needs
# (plus TRIGGER so the built-in mysqldump backup can dump the activity-feed
# triggers). Schema changes are performed exclusively by the root user via
# Alembic at backend startup, so CREATE/ALTER/INDEX/DROP are NOT granted.

set -e

mysql --protocol=socket -uroot -hlocalhost "--password=${MYSQL_ROOT_PASSWORD}" <<-EOSQL
    CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
    REVOKE ALL PRIVILEGES, GRANT OPTION FROM '${MYSQL_USER}'@'%';
    GRANT SELECT, INSERT, UPDATE, DELETE, TRIGGER
        ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'%';
    FLUSH PRIVILEGES;
EOSQL

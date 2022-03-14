#!/bin/bash
# Adapted from: https://stackoverflow.com/a/56040892
DBNAME=trac

# ticket_change takes ~5 minutes (140k entries)
for table_name in attachment ticket ticket_change
do
  pg_dump --file "results_dump.sql" --no-password --verbose --format=p --create --clean --disable-dollar-quoting --inserts --column-inserts --section=pre-data --section=data --no-owner  --table "public.${table_name}" $DBNAME

  # Remove public. prefix from table name
  sed -i "s/public\.${table_name}/${table_name}/g" results_dump.sql

  # Some clean ups
  sed -i '/^SET/d' results_dump.sql
  sed -i '/^SELECT pg_catalog./d' results_dump.sql
  sed -i "/^DROP DATABASE/d" results_dump.sql
  sed -i "/^CREATE DATABASE/d" results_dump.sql
  sed -i "/^\\\\connect /d" results_dump.sql
  sed -i "/^CREATE SEQUENCE/,/\;/d" results_dump.sql
  sed -i "/^ALTER SEQUENCE/d" results_dump.sql
  sed -i "/^ALTER TABLE ONLY.*SET DEFAULT/d" results_dump.sql

  # use transactions to make it faster
  echo 'BEGIN;' | cat - results_dump.sql > temp && mv temp results_dump.sql
  echo 'END;' >> results_dump.sql

  # delete the current table
  sqlite3 results.sqlite3 "DROP TABLE IF EXISTS ${table_name};"

  # finally apply changes
  sqlite3 results.sqlite3 < results_dump.sql # && \
#  rm results_dump.sql && \
#  rm results_dump.sql.original
done




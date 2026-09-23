#!/bin/sh
# load raw csvs into postgres, then build and test the dbt project
set -e

python -m ingest.load_raw --data-dir data/raw

cd warehouse/dbt_shipsignal
dbt build --profiles-dir .

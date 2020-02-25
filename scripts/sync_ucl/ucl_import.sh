#!/bin/bash

ALYX_PATH="/var/www/alyx-main/"

set -e
echo "Downloading the cortexlab database backup"
cd $ALYX_PATH
scp ubuntu@alyx.cortexlab.net:/var/www/alyx/alyx-backups/$(date +%Y-%m-%d)/alyx_full.sql.gz ./scripts/sync_ucl/cortexlab.sql.gz
gunzip -f ./scripts/sync_ucl/cortexlab.sql.gz

echo "Reinitialize the cortexlab database"
psql -q -U ibl_dev -h localhost -d cortexlab -c "drop schema public cascade"
psql -q -U ibl_dev -h localhost -d cortexlab -c "create schema public"
psql -h localhost -U ibl_dev -d cortexlab -f ./scripts/sync_ucl/cortexlab.sql
rm ./scripts/sync_ucl/cortexlab.sql

cd alyx
source ../venv/bin/activate
./manage.py migrate --database cortexlab
echo "Cascade deleting all non-IBL subjects"
./manage.py shell < ../scripts/sync_ucl/prune_cortexlab.py
echo "Load pruned cortexlab data into ibl"
./manage.py loaddata ../scripts/sync_ucl/cortexlab_pruned.json 

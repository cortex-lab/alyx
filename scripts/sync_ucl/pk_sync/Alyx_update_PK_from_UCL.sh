#!/bin/bash

IBL_DATABASE="ibl"
ALYX_PATH="/var/www/alyx-main/"

set -e
echo "Downloading the cortexlab database backup"
cd $ALYX_PATH

scp ubuntu@alyx.cortexlab.net:/var/www/alyx/alyx-backups/$(date +%Y-%m-%d)/alyx_full.sql.gz ./scripts/sync_ucl/cortexlab.sql.gz

echo "Reinitialize the cortexlab database"
psql -q -U ibl_dev -h localhost -d cortexlab -c "drop schema public cascade"
psql -q -U ibl_dev -h localhost -d cortexlab -c "create schema public"
gunzip ./scripts/sync_ucl/cortexlab.sql.gz
psql -h localhost -U ibl_dev -d cortexlab -f ./scripts/sync_ucl/cortexlab.sql
rm ./scripts/sync_ucl/cortexlab.sql

cd alyx
source ../venv/bin/activate
echo "DEV - REINIT PKS: full database initialisation"
# update primary keys in the current database
./manage.py shell < ../scripts/sync_ucl/pk_sync/Alyx_update_PK_from_UCL.py
# Deletes the full dev database
psql -q -U ibl_dev -h localhost -d $IBL_DATABASE -c "drop schema public cascade"
psql -q -U ibl_dev -h localhost -d $IBL_DATABASE -c "create schema public"
# Apply all the migrations from scratch on the empty database
./manage.py makemigrations # should show no changes detected
./manage.py migrate
./manage.py shell -c "from data.models import DataFormat; DataFormat.objects.get(name='unknown').delete()"
./manage.py shell -c "from data.models import DatasetType; DatasetType.objects.get(name='unknown').delete()"
# Load everything in the database
psql -q -U ibl_dev -h localhost -d $IBL_DATABASE -c "delete from auth_group_permissions; delete from auth_permission; delete from django_admin_log; delete from django_content_type;"
echo "DEV - LOAD DB w/ new PKS"
./manage.py loaddata  ../scripts/sync_ucl/ibl-alyx-pkupdate-after.json

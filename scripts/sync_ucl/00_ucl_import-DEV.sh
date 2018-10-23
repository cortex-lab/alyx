#!/bin/bash
set -e
echo "Downloading the cortexlab database backup"
cd /var/www/alyx-dev/

scp ubuntu@alyx.cortexlab.net:/var/www/alyx/alyx-backups/$(date +%Y-%m-%d)/alyx_full.sql.gz ./scripts/sync_ucl/cortexlab.sql.gz

echo "Reinitialize the cortexlab databse"
#NB: recreating the temporary database has to be done after a migration !!
psql -q -U ibl_dev -h localhost -d cortexlab -c "drop schema public cascade"
psql -q -U ibl_dev -h localhost -d cortexlab -c "create schema public"
gunzip ./scripts/sync_ucl/cortexlab.sql.gz
psql -h localhost -U ibl_dev -d cortexlab -f ./scripts/sync_ucl/cortexlab.sql
rm ./scripts/sync_ucl/cortexlab.sql


cd alyx
source ../venv/bin/activate
################# DO THIS ONCE THEN REMOVE THIS FOR ALYX-MAIN
echo "DEV: json dump full cortexlab..."
./manage.py dumpdata -e contenttypes -e auth.permission -e reversion.version -e reversion.revision -e admin.logentry -e authtoken.token -e auth.group --indent 1 --database cortexlab -o ../scripts/sync_ucl/cortexlab.json
echo "DEV: json dump full IBL..."
./manage.py dumpdata -e contenttypes -e auth.permission -e reversion.version -e reversion.revision -e admin.logentry -e authtoken.token  --indent 1  -o ../scripts/sync_ucl/ibl-alyx-dev.json
##################
echo "Cascade deleting all non-IBL subjects"
./manage.py shell < ../scripts/sync_ucl/prune_cortexlab.py

#################  DO THIS ONCE THEN REMOVE THIS FOR ALYX-MAIN
echo "DEV - REINIT PKS"
# update primary keys in the current database
./manage.py shell < ../scripts/sync_ucl/Alyx_update_PK_from_UCL.py
# Deletes the full dev database
psql -q -U ibl_dev -h localhost -d ibl_dev -c "drop schema public cascade"
psql -q -U ibl_dev -h localhost -d ibl_dev -c "create schema public"
# Apply all the migrations from scratch on the empty database
./manage.py makemigrations # should show no changes detected
./manage.py migrate 
./manage.py shell -c "from data.models import DataFormat; DataFormat.objects.get(name='unknown').delete()"
./manage.py shell -c "from data.models import DatasetType; DatasetType.objects.get(name='unknown').delete()"
# Load everything in the database
echo "DEV - LOAD DB w/ new PKS"
./manage.py loaddata  ../scripts/sync_ucl/ibl-alyx-dev-pkucl.json
##################
echo "Load pruned cortexlab data into ibl"
./manage.py loaddata ../scripts/sync_ucl/cortexlab_pruned.json 

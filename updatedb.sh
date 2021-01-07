#scp ibl:/mnt/xvdf/alyx-backups/$(date +%Y-%m-%d)/alyx_full.sql.gz .
#alyx/manage.py reset_db --noinput
#gunzip -f alyx_full.sql.gz
psql -h localhost -U labdbuser -d labdb -f alyx_full.sql

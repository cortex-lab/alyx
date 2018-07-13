scp cone:/var/www/alyx/alyx-backups/$(date +%Y-%m-%d)/alyx_full.sql.gz .
./manage.py reset_db
gunzip alyx_full.sql.gz
psql -h localhost -U cyrille -d alyx -f alyx_full.sql

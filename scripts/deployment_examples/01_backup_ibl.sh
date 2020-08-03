backup_dir="/mnt/xvdf/alyx-backups/$(date +%Y-%m-%d)"
mkdir -p "$backup_dir"

# Full SQL dump.
/usr/bin/pg_dump -cOx -U ibl_ro -h localhost ibl -f "$backup_dir/alyx_full.sql"
gzip -f "$backup_dir/alyx_full.sql"

# Full django JSON dump.
source /var/www/alyx-main/venv/bin/activate
python /var/www/alyx-main/alyx/manage.py dumpdata -e contenttypes -e auth.permission -e reversion.version -e reversion.revision -e admin.logentry --indent 1 > "$backup_dir/alyx_full.json"
gzip -f "$backup_dir/alyx_full.json"

# Send the files to the FlatIron server
scp -P 61022 "$backup_dir/alyx_full.sql.gz" alyx@ibl.flatironinstitute.org:/mnt/ibl/json/$(date +%Y-%m-%d)_alyxfull.sql.gz
#scp -P 61022 "$backup_dir/alyx_full.json.gz" alyx@ibl.flatironinstitute.org:/mnt/ibl/json/$(date +%Y-%m-%d)_alyxfull.json.gz
scp -P 61022 "$backup_dir/alyx_full.json.gz" alyx@ibl.flatironinstitute.org:/mnt/ibl/json/alyxfull.json.gz

# Human-readable TSV backup and Google Spreadsheets backup.
# /var/www/alyx/alyx/bin/python /var/www/alyx/alyx/manage.py backup /var/www/alyx/alyx-backups/


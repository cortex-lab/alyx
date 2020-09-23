backup_dir="/mnt/xvdf/alyx-backups/$(date +%Y-%m-%d)"
mkdir -p "$backup_dir"

# Full SQL dump.
/usr/bin/pg_dump -cOx -U ibl_ro -h localhost ibl -f "$backup_dir/alyx_full.sql"
gzip -f "$backup_dir/alyx_full.sql"
scp -P 61022 "$backup_dir/alyx_full.sql.gz" alyx@ibl.flatironinstitute.org:/mnt/ibl/json/$(date +%Y-%m-%d)_alyxfull.sql.gz

# Full django JSON dump, used by datajoint
source /var/www/alyx-main/venv/bin/activate
python /var/www/alyx-main/alyx/manage.py dumpdata \
    -e contenttypes -e auth.permission \
    -e reversion.version -e reversion.revision -e admin.logentry \
    -e actions.ephyssession \
    -e actions.notification \
    -e actions.notificationrule \
    -e actions.virusinjection \
    -e data.download \
    -e experiments.brainregion \
    -e jobs.task \
    -e misc.note \
    -e subjects.subjectrequest \
    --indent 1 -o "alyx_full.json"
gzip -f "alyx_full.json"
scp -P 61022 "alyx_full.json.gz" alyx@ibl.flatironinstitute.org:/mnt/ibl/json/alyxfull.json.gz

# clean up the backups on AWS instance
python /var/www/alyx-main/scripts/deployment_examples/99_purge_duplicate_backups.py

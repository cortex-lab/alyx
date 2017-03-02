#!/usr/bin/env bash
today=`date +%Y-%m-%d`
root_dir=$1
if [ -z "$1" ]; then
    root_dir='.'
fi
output_dir="$root_dir/alyx-backups/$today/"
mkdir -p $output_dir
host='rod.cortexlab.net'
user='alyx_ro'
database='alyx'
port=5432
for name in queries/*.sql; do
    bn=$(basename $name)
    bn_noext=${bn%.*}
    psql -h $host -U $user -p $port -d $database -c "\copy ($(cat $name)) to '$output_dir/$bn_noext.tsv' with CSV DELIMITER E'\t' header encoding 'utf-8'"
done
echo "Backup done in $output_dir"

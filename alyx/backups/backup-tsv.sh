#!/usr/bin/env bash
output_dir='tsv_files'
mkdir -p $output_dir
host='rod.cortexlab.net'
user='alyx_ro'
port=5432
database='alyx'
for name in queries/*.sql; do
    bn=$(basename $name)
    bn_noext=${bn%.*}
    psql -h $host -U $user -p $port -d $database -c "\copy ($(cat $name)) to '$output_dir/$bn_noext.tsv' with CSV DELIMITER E'\t' header encoding 'utf-8'"
done

#!/usr/bin/env bash
output_dir='tsv_files'
mkdir -p $output_dir
for name in queries/*.sql; do
    bn=$(basename $name)
    bn_noext=${bn%.*}
    psql -h localhost -U cyrille -p 5432 -d labdb -c "\copy ($(cat $name)) to '$output_dir/$bn_noext.tsv' with CSV DELIMITER E'\t' header encoding 'utf-8'"
done

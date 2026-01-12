This directory contains anonymized data used in database tests.

`all_dumped_anon.json.gz` is obtained with:

```sh
python manage.py dump --test
```

To import the data into a non-production database, outside of tests:

```sh
python manage.py reset_db
python manage.py migrate
python manage.py loaddata ../data/all_dumped_anon.json.gz
```

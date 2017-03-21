all: serve

serve:
	./manage.py runserver

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean: clean-pyc

rmmigrations: clean
	rm */migrations/*.py

migrate:
	./manage.py migrate
	./manage.py makemigrations actions behavior data electrophysiology equipment imaging misc subjects
	./manage.py migrate

delete_all:
	psql -d postgres -c "DROP DATABASE alyx;" && psql -d postgres -c "CREATE DATABASE alyx;"

import_fixtures:
	python ../data/importer.py
	./manage.py loaddata ../data/json/*.json
	python make_zygosities.py

reset_all: clean-pyc rmmigrations delete_all migrate import_fixtures

dump_all:
	./manage.py dumpdata -e contenttypes -e auth.permission --indent 1 --natural-foreign --natural-primary -o ../data/all_dumped.json

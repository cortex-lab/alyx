all: serve

serve:
	python3 manage.py runserver

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean: clean-pyc

rmmigrations: clean
	rm */migrations/*.py

migrate:
	python3 manage.py migrate
	python3 manage.py makemigrations actions behavior data electrophysiology equipment imaging misc subjects
	python3 manage.py migrate

delete_all:
	psql -d postgres -c "DROP DATABASE alyx;" && psql -d postgres -c "CREATE DATABASE alyx;"

import_fixtures:
	python3 ../data/importer.py
	python3 manage.py loaddata ../data/json/*.json
	python3 make_zygosities.py

reset_all: delete_all migrate import_fixtures

dump_all:
	python3 manage.py dumpdata -e contenttypes -e auth.permission --indent 1 --natural-foreign --natural-primary -o ../data/all_dumped.json

test:
	./manage.py test -k


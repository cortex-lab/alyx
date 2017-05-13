all: serve

serve:
	python manage.py runserver

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean: clean-pyc

rmmigrations: clean
	rm */migrations/0*.py

migrate:
	python manage.py migrate
	python manage.py makemigrations actions behavior data electrophysiology equipment imaging misc subjects
	python manage.py migrate

dump:
	python manage.py dumpdata -e contenttypes -e auth.permission -e admin.logentry --indent 1 -o ../data/all_dumped.json
	python ../data/anonymize.py ../data/all_dumped.json
	gzip -fk ../data/all_dumped_anon.json

test:
	python manage.py test -k
	flake8

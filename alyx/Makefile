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

test:
	python manage.py test -k
	flake8

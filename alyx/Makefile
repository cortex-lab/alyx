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
	python manage.py makemigrations equipment misc subjects actions data imaging behavior electrophysiology
	python manage.py migrate

test:
	python manage.py test -k -n
	flake8

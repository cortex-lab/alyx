#!/usr/bin/env bash
./manage.py dumpdata actions.proceduretype > ../data/init-fixtures/actions.proceduretype.json

./manage.py dumpdata data.datarepositorytype > ../data/init-fixtures/data.datarepositorytype.json
./manage.py dumpdata data.datarepository > ../data/init-fixtures/data.datarepository.json
./manage.py dumpdata data.dataformat > ../data/init-fixtures/data.dataformat.json
./manage.py dumpdata data.datasettype > ../data/init-fixtures/data.datasettype.json

./manage.py dumpdata misc.lab > ../data/init-fixtures/misc.lab.json

./manage.py dumpdata subjects.project > ../data/init-fixtures/subjects.project.json
./manage.py dumpdata subjects.source > ../data/init-fixtures/subjects.source.json

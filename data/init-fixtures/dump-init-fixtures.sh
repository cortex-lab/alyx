#!/usr/bin/env bash
./manage.py dumpdata actions.proceduretype --indent 1 -o ../data/init-fixtures/actions.proceduretype.json
./manage.py dumpdata data.datarepositorytype --indent 1 -o ../data/init-fixtures/data.datarepositorytype.json
./manage.py dumpdata data.datarepository --indent 1 -o ../data/init-fixtures/data.datarepository.json
./manage.py dumpdata data.dataformat --indent 1 -o ../data/init-fixtures/data.dataformat.json
./manage.py dumpdata data.datasettype --indent 1 -o ../data/init-fixtures/data.datasettype.json
./manage.py dumpdata misc.lab --indent 1 -o ../data/init-fixtures/misc.lab.json
./manage.py dumpdata subjects.project --indent 1 -o ../data/init-fixtures/subjects.project.json
./manage.py dumpdata subjects.source --indent 1 -o ../data/init-fixtures/subjects.source.json

#!/usr/bin/env bash
cd ../alyx
source ../alyxvenv/bin/activate

./manage.py loaddata ./actions/fixtures/actions.proceduretype.json
./manage.py loaddata ./actions/fixtures/actions.watertype.json
./manage.py loaddata ./actions/fixtures/actions.cullreason.json

./manage.py loaddata ./data/fixtures/data.datarepositorytype.json
./manage.py loaddata ./data/fixtures/data.dataformat.json
./manage.py loaddata ./data/fixtures/data.datasettype.json

./manage.py loaddata ./misc/fixtures/misc.cagetype.json
./manage.py loaddata ./misc/fixtures/misc.enrichment.json
./manage.py loaddata ./misc/fixtures/misc.food.json

./manage.py loaddata ./subjects/fixtures/subjects.source.json

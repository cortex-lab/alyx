#!/usr/bin/env bash
cd ../alyx
source ../alyxvenv/bin/activate

./manage.py dumpdata actions.proceduretype --indent 1 -o ./actions/fixtures/actions.proceduretype.json
./manage.py dumpdata actions.watertype --indent 1 -o ./actions/fixtures/actions.watertype.json
./manage.py dumpdata actions.cullreason --indent 1 -o ./actions/fixtures/actions.cullreason.json
./manage.py dumpdata actions.cullmethod --indent 1 -o ./actions/fixtures/actions.cullmethod.json

./manage.py dumpdata data.datarepositorytype --indent 1 -o ./data/fixtures/data.datarepositorytype.json
./manage.py dumpdata data.dataformat --indent 1 -o ./data/fixtures/data.dataformat.json
# NB: need to null created_by field
./manage.py dumpdata data.datasettype --indent 1 -o ./data/fixtures/data.datasettype.json

./manage.py dumpdata misc.cagetype --indent 1 -o ./misc/fixtures/misc.cagetype.json
./manage.py dumpdata misc.enrichment --indent 1 -o ./misc/fixtures/misc.enrichment.json
./manage.py dumpdata misc.food --indent 1 -o ./misc/fixtures/misc.food.json

./manage.py dumpdata subjects.source --indent 1 -o ./subjects/fixtures/subjects.source.json

./manage.py dumpdata experiments.coordinatesystem --indent 1 -o ./experiments/fixtures/experiments.coordinatesystem.json
./manage.py dumpdata experiments.probemodel --indent 1 -o ./experiments/fixtures/experiments.probemodel.json
./manage.py dumpdata experiments.brainregions --indent 1 -o ./experiments/fixtures/experiments.brainregions.json

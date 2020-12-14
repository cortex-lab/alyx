#!/bin/bash

# init DB
./manage.py migrate
./manage.py shell -c "from misc.models import LabMember; LabMember.objects.create_superuser('admin', 'admin@example.com', 'admin')"
./load-init-fixtures.sh

# launch django server
./manage.py runserver 0.0.0.0:80

DBNAME='%DBNAME%'
DBUSER='%DBUSER%'
FILENAME='alyx.sql.gz'

gunzip $FILENAME
alyxvenv/bin/python alyx/manage.py reset_db
psql -h localhost -U $DBUSER -d $DBNAME -f ${FILENAME%.*}

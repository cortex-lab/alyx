DBNAME='labdb'
DBUSER='labdbuser'
FILENAME='alyx.sql'

pg_dump -cOx -U $DBUSER -h localhost $DBNAME -f $FILENAME
gzip $FILENAME

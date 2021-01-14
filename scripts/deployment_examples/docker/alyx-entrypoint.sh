#! /bin/sh

# alyx entrypoint script
# ====================== 

# globals
# -------

dbdump="/dump.sql.gz"
dbloaded="/alyx/alyx/db_loaded"
sucreated="/alyx/alyx/superuser_created"

err_exit() { echo "error: $*"; exit 1; }

# checks
# ------

[ -z "$PGUSER" ] && err_exit "PGUSER unset";
[ -z "$PGHOST" ] && err_exit "PGPASSWORD unset";
[ -z "$PGPASSWORD" ] && err_exit "PGPASSWORD unset";
[ ! -f "${dbdump}" ] && err_exit "no database dump in $dbdump";

# create/load database
# --------------------

echo '# => database create/load'

if [ ! -f "${dbloaded}" ]; then

	echo '# ==> database create'
	createdb alyx

	echo '# ==> database load'
	gzip -dc ${dbdump} |psql -d alyx

	touch ${dbloaded}
fi

# configure alyx/django
# ---------------------

echo '# => configuring alyx'

if [ ! -f "$sucreated" ]; then

	echo '# ==> configuring settings_secret.py'

	sed \
		-e "s/%SECRET_KEY%/0xdeadbeef/" \
		-e "s/%DBNAME%/alyx/" \
		-e "s/%DBUSER%/$PGUSER/" \
		-e "s/%DBPASSWORD%/$PGPASSWORD/" \
		-e "s/127.0.0.1/$PGHOST/" \
		< /alyx/alyx/alyx/settings_secret_template.py \
		> /alyx/alyx/alyx/settings_secret.py

	echo '# ==> creating alyx superuser'

	/alyx/alyx/manage.py createsuperuser \
		--no-input \
		--username admin \
		--email admin@localhost

	echo '# ==> setting alyx superuser password'

	# note on superuser create: 
	#
	# - no-input 'createsuperuser' creates without password
	# - cant set password from cli here or in setpassword command
	# - so script reset via manage.py shell
	# - see also: 
	#   https://stackoverflow.com/questions/6358030/\
	#     how-to-reset-django-admin-password

	/alyx/alyx/manage.py shell <<-EOF

	from django.contrib.auth import get_user_model
	User = get_user_model()
	admin = User.objects.get(username='admin')
	admin.set_password('$PGPASSWORD')
	admin.save()
	exit()

EOF

	touch ${sucreated}
fi

# start alyx
# ----------

echo '# => starting alyx'

/alyx/alyx/manage.py makemigrations
/alyx/alyx/manage.py migrate

/alyx/alyx/manage.py runserver --insecure 0.0.0.0:8000


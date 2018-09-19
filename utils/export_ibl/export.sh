echo "Recreating the temporary database"
psql -h localhost -U cyrille -d alyx -c 'DROP DATABASE IF EXISTS alyx_ibl_tmp;'
psql -h localhost -U cyrille -d alyx -c 'CREATE DATABASE alyx_ibl_tmp WITH TEMPLATE alyx OWNER cyrille;'
echo "Cascade deleting all non-IBL subjects"
python alyx/manage.py shell -c "from subjects.models import Subject; Subject.objects.using('ibl_tmp').exclude(projects__name__icontains='ibl').delete()"
echo "Creating the JSON dump"
python alyx/manage.py dumpdata -e contenttypes -e auth.permission -e reversion.version -e reversion.revision -e admin.logentry -e authtoken.token -e auth.group --indent 1 --database ibl_tmp -o dump_ibl.json

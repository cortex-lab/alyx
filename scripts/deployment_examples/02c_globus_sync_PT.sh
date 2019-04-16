cd /var/www/alyx-main/
source ./venv/bin/activate
cd alyx

./manage.py files bulksync --project=ibl_danlab

./manage.py files bulktransfer --project=ibl_danlab

sleep 900

./manage.py files bulksync --project=ibl_danlab

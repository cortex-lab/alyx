cd /var/www/alyx-main/
source ./venv/bin/activate
cd alyx

./manage.py files bulksync --lab=danlab

./manage.py files bulktransfer --lab=danlab

sleep 900

./manage.py files bulksync --lab=danlab

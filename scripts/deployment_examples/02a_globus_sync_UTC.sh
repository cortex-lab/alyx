cd /var/www/alyx-main/
source ./venv/bin/activate
cd alyx

./manage.py files bulksync --project=ibl_cortexlab
./manage.py files bulksync --project=ibl_mainenlab

./manage.py files bulktransfer --project=ibl_cortexlab
./manage.py files bulktransfer --project=ibl_mainenlab

sleep 900

./manage.py files bulksync --project=ibl_cortexlab
./manage.py files bulksync --project=ibl_mainenlab

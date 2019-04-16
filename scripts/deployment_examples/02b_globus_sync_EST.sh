cd /var/www/alyx-main/
source ./venv/bin/activate
cd alyx

./manage.py files bulksync --project=ibl_churchlandlab
./manage.py files bulksync --project=ibl_wittenlab
./manage.py files bulksync --project=ibl_angelakilab

./manage.py files bulktransfer --project=ibl_churchlandlab
./manage.py files bulktransfer --project=ibl_wittenlab
./manage.py files bulktransfer --project=ibl_angelakilab

sleep 900

./manage.py files bulksync --project=ibl_churchlandlab
./manage.py files bulksync --project=ibl_wittenlab
./manage.py files bulksync --project=ibl_angelakilab

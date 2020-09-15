cd /var/www/alyx-main/
source ./venv/bin/activate
cd alyx

./manage.py files bulksync --lab=cortexlab
./manage.py files bulktransfer --lab=cortexlab

./manage.py files bulksync --lab=mainenlab
./manage.py files bulktransfer --lab=mainenlab

./manage.py files bulksync --lab=mrsicflogellab
./manage.py files bulktransfer --lab=mrsicflogellab

./manage.py files bulksync --lab=hoferlab
./manage.py files bulktransfer --lab=hoferlab

sleep 900

./manage.py files bulksync --lab=cortexlab
./manage.py files bulksync --lab=mainenlab
./manage.py files bulksync --lab=mrsicflogellab
./manage.py files bulksync --lab=hoferlab

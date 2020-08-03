cd /var/www/alyx-main/
source ./venv/bin/activate
cd alyx

./manage.py files bulksync --lab=danlab
./manage.py files bulksync --lab=steinmetzlab

./manage.py files bulktransfer --lab=danlab
./manage.py files bulktransfer --lab=steinmetzlab

sleep 900

./manage.py files bulksync --lab=danlab
./manage.py files bulksync --lab=steinmetzlab

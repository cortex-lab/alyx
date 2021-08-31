cd /var/www/alyx-main/
source ./venv/bin/activate
cd alyx

./manage.py files bulksync --lab=danlab
./manage.py files bulksync --lab=steinmetzlab
./manage.py files bulksync --lab=churchlandlab_ucla

./manage.py files bulktransfer --lab=danlab
./manage.py files bulktransfer --lab=steinmetzlab
./manage.py files bulktransfer --lab=churchlandlab_ucla

sleep 900

./manage.py files bulksync --lab=danlab
./manage.py files bulksync --lab=steinmetzlab
./manage.py files bulksync --lab=churchlandlab_ucla

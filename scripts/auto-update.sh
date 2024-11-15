# 1/ activate environment
source /var/www/alyx-main/venv/bin/activate;
cd /var/www/alyx-main/alyx
# 2/ pull the changes from github (on your favourite branch)
git stash
git pull
git stash pop
# 3/ install any new requirements
pip install -r requirements.txt
# 4/ update database if scheme changes
./manage.py makemigrations
./manage.py migrate
# 5/ If new fixtures load them in the database
../scripts/load-init-fixtures.sh
# 6/ if new tables change the postgres permissions
./manage.py set_db_permissions
./manage.py set_user_permissions
# 7/ if there were updates to the Django version collect the static files
./manage.py collectstatic --no-input
# 8/ restart the apache server
sudo service apache2 reload

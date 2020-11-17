# 1/ activate environment
source /var/www/alyx-main/venv/bin/activate;
cd /var/www/alyx-main/alyx
# 2/ pull the changes from github (on your favourite branch)
git stash
git pull
git stash pop
# 3/ update database if scheme changes
./manage.py makemigrations
./manage.py migrate
# 4/ If new fixtures load them in the database
../scripts/load-init-fixtures.sh
# 5/ if new tables change the postgres permissions
./manage.py set_db_permissions
./manage.py set_user_permissions
# 6/ restart the apache server
sudo service apache2 reload

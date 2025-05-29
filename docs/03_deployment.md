
# Deployments how-to's guides

If the database needs to be served on the web, one tested solution is to use an apache web server.


## Install a development version of Alyx

TODO: change settings.py to populate env file and link the following settings files
```shell
cp ./deploy/docker/settings-deploy.py alyx/alyx/settings.py
cp ./deploy/docker/settings_lab-deploy.py alyx/alyx/settings_lab.py
```


Note that the postgres username and password are distinct from Alyx (Django) users and password. There is only one postgres user that is only used locally for maintenance task or by Django.

### Ubuntu or Debian based Linux
Go to the directory of your choice (for example: `/var/www/alyx-local`) and follow the installation guide

Install required packages
```shell
# install required packages
sudo apt-get install python3-pip python3-dev libpq-dev postgresql postgresql-contrib virtualenv
```

Create log folder and folder for storing uploaded content.
```shell
sudo mkdir /var/log/alyx
sudo mkdir uploaded
sudo chmod 775 -fR uploaded
sudo chown www-data:www-data -fR uploaded
```

Clone the repository and install the environment
```shell
git clone https://github.com/cortex-lab/alyx.git
virtualenv alyxvenv --python=python3
source ./alyxvenv/bin/activate
pip install -r requirements.txt
````

Install Alyx, check installation. Then load init fixtures in the database and launch the server.
```shell
python setup.py
    ...
    $ Enter a database name [alyxlocal]:
    $ Enter a postgres username [alyxlocaluser]:
    $ Enter a postgres password:
    ...
python alyx/manage.py collectstatic --noinput
python alyx/manage.py check

cd alyx
../scripts/load-init-fixtures.sh

python manage.py runserver
```
NB: the password above is the postgres database user password. It is used by Django only to connect to the database, and is distinct from any user password on admin website.

You can then visit http://localhost:8000/admin, connect as `admin:admin` (ie. username admin and password admin) and update your admin interface password.

> [!WARNING]
> Alyx is by default in debug mode, meaning it is not safe to run on the the open Web. To run securly, open the `alyx/alyx/settings.py` file and set `DEBUG=False`. This enables https redirection (SSL certificates required) and various cross-site scripting protections. Debug mode is adequate if running Alyx on a local network or secure institute intranet.

### macOS

* Install Python 3 (using the [official installer](https://www.python.org/downloads/mac-osx/), or [conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/macos.html)). Make sure pip is installed.
* Install [Postgress.app](https://postgresapp.com/downloads.html)
* Open a Terminal.
* Type `git`, press Enter, and follow the instructions to install git.
* Type `sudo touch /var/log/alyx.log; sudo chmod 776 /var/log/alyx.log;`
* Type `sudo mkdir -p /etc/paths.d && echo /Applications/Postgres.app/Contents/Versions/latest/bin | sudo tee /etc/paths.d/postgresapp`
* Open Postgres.app, and press initialize/start to start the server.
* Close the terminal, open a new one, and go to a directory where you'll download alyx into.
* Type `git clone git@github.com:cortex-lab/alyx.git`
* `cd alyx`
* Type `pip install -r requirements.txt`
* Type `pip uninstall python-magic`
* Type `pip install python-magic-bin`
* Type `python setup.py`, and follow the instructions.
* If everything went well you should see no error message and the message `Alyx setup successful <3`.
* Type `python alyx/manage.py collectstatic --noinput`. You should see a message about files being copied to ./alyx/alyx/static
* Type `python alyx/manage.py check`. You should see the message `System check identified no issues (0 silenced).`
* To reinitialize your local database, type `alyx/manage.py reset_db --noinput`
* To clone an existing alyx database from a backup, get an `alyx_full.sql.gz` in your alyx folder, and type `gunzip -f alyx_full.sql.gz`
* Then type `psql -h localhost -U labdbuser -d labdb -f alyx_full.sql` — this command might take a few minutes with large backups
* Type `python manage.py migrate`
* To run the development server, type `python alyx/manage.py runserver`
* Go to `http://localhost:8000/admin/`

> [!WARNING]
> Alyx is by default in debug mode, meaning it is not safe to run on the the open Web. To run securly, open the `alyx/alyx/settings.py` file and set `DEBUG=False`. This enables https redirection (SSL certificates required) and various cross-site scripting protections. Debug mode is adequate if running Alyx on a local network or secure institute intranet.

## Advanced topics

### Building the docker containers

We have built our images on top of the apache2 images as it is the webserver we currently use. 
However as shown in the getting started section, those images are suitable for use with different servers such as gunicorn.

```shell
# need to be in the build folder to copy some apache settings
cd ./alyx/deploy/docker/

# builds the base container
docker buildx build . \
  --platform linux/amd64 \
  --tag internationalbrainlab/alyx_apache_base:latest \
  -f ./Dockerfile_base

# builds the top layer
docker buildx build . \
  --platform linux/amd64 \
  --tag internationalbrainlab/alyx_apache:latest \
  -f ./Dockerfile \
  --build-arg alyx_branch=deploy \
  --no-cache
```

### Apache webserver and interaction with wsgi

Put the [site configuration](_static/001-alyx.conf) here: `/etc/apache2/sites-available/001-alyx.conf`
-   make sure the paths within the file match the alyx installation path.
-   update ServerName parameter `ServerName  alyx.internationalbrainlab.org`
-   it should match the `alyx/alyx/settings_lab.py` `ALLOWED_HOSTS` parameter


Activate the website

    sudo a2ensite
        001-alyx-main

Restart the server, 2 commands are provided here for reference. Reload is recommended on a running production server as 
it should not interrupt current user transactions if any.


    sudo /etc/init.d/apache2 restart
    sudo /etc/init.d/apache2 reload


Location of error logs for apache if it fails to start

    /var/log/apache2/

---

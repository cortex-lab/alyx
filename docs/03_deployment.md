
# Deployments how-to's guides

For a simple deployment using a containerized version of Alyx interacting with a containerized database, refer to the how-to guide.

For running alyx directly on the host machine, follow the instructions below.



## Install a development version of Alyx on the host machine

Clone the alyx repository from [here](https://github.com/cortex-lab/alyx). 
```shell
git clone https://github.com/cortex-lab/alyx.git
cd alyx
```

Create a virtual environment using uv and install the repo in an editable mode using `uv pip install -e .`



Copy the settings files from the deploy folder inside of the alyx project. Those files are ignored by git.

```shell
cp ./deploy/docker/settings-deploy.py alyx/alyx/settings.py
cp ./deploy/docker/settings_lab-deploy.py alyx/alyx/settings_lab.py
```

Copy the environment template file and edit the path to the logs
```
cp ./alyx/alyx/environment_template.env ./alyx/alyx/.env
vi ./alyx/alyx/.env
```
In the environment file, you need to provide a writable log directory and change the postgres host to localhost.
```shell
APACHE_LOG_DIR=/Users/olivier/scratch/alyxlogs
POSTGRES_HOST=localhost
```

**Note:** On macOS, if there is a local version of the postgres already installed and you want to use the containerized version of postgres, it is also good to change the variable `POSTGRES_PORT` in the .env file to 5433. And export the variable as well using `export POSTGRES_PORT=5433` in the shell where the following commands will be launched.

First we will start the docker service containing the database and make sure we can connect to it using the current `.env` settings.
The `showmigrations` command will fail if the database is not available.
```shell
docker compose -f ./deploy/docker-compose-postgres.yaml up -d
cd alyx
python manage.py showmigrations
```

Next we can start collecting the static files, migrating the database, setup the minimum amount of data and create a superuser.

```shell
python manage.py collectstatic --noinput
python manage.py check
python manage.py migrate
../scripts/load-init-fixtures.sh
python manage.py createsuperuser
python manage.py runserver
```
NB: the password above is the postgres database user password. It is used by Django only to connect to the database, and is distinct from any user password on admin website.

You can then visit http://localhost:8000/admin, connect with your superuser credentials.


## Building the docker containers

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

## Advanced topics


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

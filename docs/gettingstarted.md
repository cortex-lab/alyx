# Getting Started

The example details how to
1. install a local instance of Alyx 
2. initialize it with the fixtures 
3. register some local data to it
4. using the ONE-api, load the registered data

Requirements: this tutorial works on Linux as it relies on installing postgres and Django.

The `setup.py` script sets up postgres (it creates the database and postgres user), it creates the settings files
-   `alyx/alyx/settings_secret.py`
-   `alyx/alyx/settings_lab.py`
-   `alyx/alyx/settings.py`


Note that the postgres username and password are distinct from Alyx (Django) users and password. There is only one postgres user that is only used locally for maintenance task or by Django.


## Install a local instance of Alyx

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
python alyx/manage.py check

cd alyx
../scripts/load-init-fixtures.sh

python manage.py runserver
```

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
* Type `python alyx/manage.py check`. You should see the message `System check identified no issues (0 silenced).`
* To reinitialize your local database, type `alyx/manage.py reset_db --noinput`
* To clone an existing alyx database from a backup, get an `alyx_full.sql.gz` in your alyx folder, and type `gunzip -f alyx_full.sql.gz`
* Then type `psql -h localhost -U labdbuser -d labdb -f alyx_full.sql` — this command might take a few minutes with large backups
* Type `python manage.py migrate`
* To run the development server, type `python alyx/manage.py runserver`
* Go to `http://localhost:8000/admin/`



## Accessing the web admin interface
Then, go to `http://localhost:8000/admin`, and log in with `admin:admin`. You can change your password and create users and user groups.




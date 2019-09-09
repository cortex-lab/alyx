# alyx

[![Build Status on master](https://travis-ci.org/cortex-lab/alyx.svg?branch=master)](https://travis-ci.org/cortex-lab/alyx)
[![Build Status on dev](https://travis-ci.org/cortex-lab/alyx.svg?branch=dev)](https://travis-ci.org/cortex-lab/alyx)

Database for experimental neuroscience laboratories

Documentation: http://alyx.readthedocs.io


## Installation

### Setup Python/Django and the database
Alyx has only been tested on Ubuntu (16.04 and 18.04). It could work on other systems but with no guarantees.

```
$ sudo apt-get update
$ sudo apt-get install python3-pip python3-dev libpq-dev postgresql postgresql-contrib virtualenv
$ sudo touch /var/log/alyx.log; sudo chmod 776 /var/log/alyx.log;
$ sudo mkdir uploaded
$ sudo chmod 775 -fR uploaded
$ sudo chown www-data:www-data -fR uploaded
$ git clone https://github.com/cortex-lab/alyx.git
$ cd alyx
$ virtualenv alyxvenv --python=python3
$ source ./alyxvenv/bin/activate
$ pip install -r requirements.txt
$ python setup.py
Enter a database name [labdb]:
Enter a postgres username [labdbuser]:
Enter a postgres password:
...
$ python alyx/manage.py check
$ python alyx/manage.py runserver

# An then initialize fixtures (ie. load default objects in the database)
cd scripts
./load-init-fixtures.sh
```

Then, go to `http://localhost:8000/admin`, and log in with `admin:admin`. You can change your password and create users and user groups.

The `setup.py` script sets up postgres (it creates the database and postgres user), it sets up the `alyx/alyx/settings_secret.py` file with the postgres database connection information, it creates the Python virtual environment with the dependencies (including django), and it creates all the required SQL tables.
Note that the postgres username and password are distinct from Alyx (Django) users and password. There is only one postgres user that is only used locally for maintenance task or by Django.

### Web deployment
Install apache, and wsgi module, then make sure it's enabled

    sudo apt-get install apache2
    sudo apt-get install python3-pip apache2 libapache2-mod-wsgi-py3
    sudo a2enmod wsgi

Put the [site configuration](docs/_static/001-alyx.conf) here: `/etc/apache2/sites-available/001-alyx.conf`
-   make sure the paths within the file match the alyx installation path.
-   update Servername parameter `ServerName  alyx.internationalbrainlab.org`
-   it should match the [alyx/alyx/settings_lab.py](alyx/alyx/settings_lab.py) `ALLOWED_HOSTS` parameter
    

Activate the website

    sudo a2ensite
        001-alyx-main

Restart the server, 2 commands are provided here for reference. Reload is recommended on a running production server as it should not interreupt current user transactions if any
.

    sudo /etc/init.d/apache2 restart
    sudo /etc/init.d/apache2 reload


Location of error logs if the server fails to start

    /var/log/apache2/

## Contribution

* Development happens on the **dev** branch
* alyx is sync with the **master** branch
* alyx-dev is sync with the **dev** branch
* Migrations files are provided by the repository
* Continuous integration is setup, to run tests locally:
    -   `./manage.py test -n` test without migrations (faster)
    -   `./manage.py test` test with migrations (recommended if model changes)

```
$ /manage.py test -n
```


## Deployment process

1. Freeze alyx-dev
2. Full test on alyx-dev with migrations
3. On Monday morning, merge dev to master
4. Update alyx-dev to master
5. Make SQL migrations  
    -   `./manage.py makemigrations`
    -   should output `No changes detected` as migrations are provided by the repository
6. Migrate
    -   `./manage.py migrate`
7. Full test on alyx-dev
8. Repeat 4,5,6,7 on alyx-main
9. If there was migrations, update database permission: `./manage.py set_db_permissions`
10. If webserver, reload Apache `sudo /etc/init.d/apache2 reload`

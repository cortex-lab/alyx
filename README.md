# alyx

[![Github Actions](https://github.com/cortex-lab/alyx/actions/workflows/main.yml/badge.svg)](https://github.com/cortex-lab/alyx/actions/)
[![Coverage Status](https://coveralls.io/repos/github/cortex-lab/alyx/badge.svg?branch=github_action)](https://coveralls.io/github/cortex-lab/alyx?branch=master)

Database for experimental neuroscience laboratories

Documentation: http://alyx.readthedocs.io


## Installation
Alyx has only been tested on Ubuntu (16.04 / 18.04 / 20.04), the latest is recommended. There are no guarantees that 
this setup will work on other systems. Assumptions made are that you have sudo permissions under an account named
`ubuntu`.

### Install apache, wsgi module, and set group and acl permissions
    sudo apt-get update    
    sudo apt-get install apache2 libapache2-mod-wsgi-py3 acl
    sudo a2enmod wsgi
    sudo adduser www-data syslog
    sudo setfacl -d -m u:www-data:rwx /var/log/
    sudo setfacl -d -m u:ubuntu:rwx /var/log/
    sudo touch /var/log/alyx.log /var/log/alyx_json.log
    sudo www-data:www-data /var/log/alyx.log /var/log/alyx_json.log

### Setup Python/Django and the database
Go to the directory of your choice (for example: `/var/www/alyx-main`)
```
sudo apt-get install python3-pip python3-dev libpq-dev postgresql postgresql-contrib virtualenv
sudo mkdir uploaded
sudo chmod 775 -fR uploaded
sudo chown www-data:www-data -fR uploaded
```
Ensure current user account has write permissions
```
git clone https://github.com/cortex-lab/alyx.git
cd alyx
mv alyx/settings_template.py alyx/settings.py
virtualenv alyxvenv --python=python3
source ./alyxvenv/bin/activate
pip install -r requirements.txt
python setup.py

    ...
    $ Enter a database name [labdb]:
    $ Enter a postgres username [labdbuser]:
    $ Enter a postgres password:
    ...

# An then initialize fixtures (ie. load default objects in the database)
cd alyx
../scripts/load-init-fixtures.sh

cd ..
python alyx/manage.py check
python alyx/manage.py runserver
```

Then, go to `http://localhost:8000/admin`, and log in with `admin:admin`. You can change your password and create users and user groups.

The `setup.py` script sets up postgres (it creates the database and postgres user), it sets up the `alyx/alyx/settings_secret.py` file with the postgres database connection information, it creates the Python virtual environment with the dependencies (including django), and it creates all the required SQL tables.
Note that the postgres username and password are distinct from Alyx (Django) users and password. There is only one postgres user that is only used locally for maintenance task or by Django.

### Apache Site Configuration
Put the [site configuration](docs/_static/001-alyx.conf) here: `/etc/apache2/sites-available/001-alyx.conf`
-   make sure the paths within the file match the alyx installation path.
-   update ServerName parameter `ServerName  alyx.internationalbrainlab.org`
-   it should match the [alyx/alyx/settings_lab.py](alyx/alyx/settings_lab.py) `ALLOWED_HOSTS` parameter


Activate the website

    sudo a2ensite
        001-alyx-main

Restart the server, 2 commands are provided here for reference. Reload is recommended on a running production server as 
it should not interrupt current user transactions if any.


    sudo /etc/init.d/apache2 restart
    sudo /etc/init.d/apache2 reload


Location of error logs for apache if it fails to start

    /var/log/apache2/

### [Optional] Setup AWS Cloudwatch Agent logging

If you are running alyx as an EC2 instance on AWS, you can easily add the AWS Cloudwatch agent to the server to ease log
evaluation and alerting. This can also be done with a non-ec2 server, but is likely not worth it unless you are already 
using Cloudwatch for other logs.

To give an overview of the installation process for an EC2 instance:
* Create an IAM role that enables the agent to collect metrics from the server and attach the role to the server.
* Download the agent package to the instance.
* Modify the CloudWatch agent configuration file, specify the metrics and the log files that you want to collect.
* Install and start the agent on your server.
* Verify in Cloudwatch 
  * you are now able to generate alerts from the metrics of interest
  * you are now shipping the logs files to your log group

Follow the latest instructions from the official [AWS Cloudwatch Agent documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Install-CloudWatch-Agent.html).

Other useful references:
* [IAM documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-vs-inline.html)
* [EC2 metadata documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-metadata.html) 

---

### [macOS] Local installation of alyx

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
9. If there were migrations, update database permission: `./manage.py set_db_permissions`
10. If webserver, reload Apache `sudo /etc/init.d/apache2 reload`

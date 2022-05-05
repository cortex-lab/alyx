# Getting Started

The example details how to install a local instance of Alyx, initialize it with the fixtures and register some local data to it.
Then using the ONE-api, load some of the data by doing a query on the database.

Requirements: this tutorial works on Linux as it relies on installing postgres and Django.

## Install a local instance of Alyx
Go to the directory of your choice (for example: `/var/www/alyx-local`)

``` shell
# install required packages 
sudo apt-get install python3-pip python3-dev libpq-dev postgresql postgresql-contrib virtualenv
# create log folder
sudo mkdir /var/log/alyx

# create folder for storing uploaded notes, and deal with permissions
sudo mkdir uploaded
sudo chmod 775 -fR uploaded
sudo chown www-data:www-data -fR uploaded
sudo touch /var/www/alyx-local/
# clone the repository and cd into it
git clone https://github.com/cortex-lab/alyx.git

# create the python virtual environment and install dependencies 
virtualenv alyxvenv --python=python3
source ./alyxvenv/bin/activate
pip install -r requirements.txt
python setup.py
    ...
    $ Enter a database name [alyxlocal]:
    $ Enter a postgres username [alyxlocaluser]:
    $ Enter a postgres password:
    ...

python alyx/manage.py check
python alyx/manage.py runserver

# An then initialize fixtures (ie. load default objects in the database)
cd alyx
../scripts/load-init-fixtures.sh
```



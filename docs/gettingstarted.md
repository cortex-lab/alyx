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
python alyx/manage.py collectstatic --noinput
python alyx/manage.py check

cd alyx
../scripts/load-init-fixtures.sh

python manage.py runserver
```
NB: the password above is the postgres database user password. It is used by Django only to connect to the database, and is distinct from any user password on admin website.

You can then visit http://localhost:8000/admin, connect as `admin:admin` (ie. username admin and password admin) and update your admin interface password.

[!WARNING]  
Alyx is by default in debug mode, meaning it is not safe to run on the the open Web. To run securly, open the `alyx/alyx/settings.py` file and set `DEBUG=False`. This enables https redirection (SSL certificates required) and various cross-site scripting protections. Debug mode is adequate if running Alyx on a local network or secure institute intranet.

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

[!WARNING]  
Alyx is by default in debug mode, meaning it is not safe to run on the the open Web. To run securly, open the `alyx/alyx/settings.py` file and set `DEBUG=False`. This enables https redirection (SSL certificates required) and various cross-site scripting protections. Debug mode is adequate if running Alyx on a local network or secure institute intranet.

## Interaction with the database

There are 3 main ways to interact with the database, listed below:

|   	   | **Where**   	| **Who**  	|  **Notes**
| ---	| ---	| ---	| ---
| **Django Shell**	| server only	| admin only	| This hits the database directly. It is a very powerful way to do maintenance at scale, with the risks associated. Run the `./manage.py shell` Django command to access the Ipython shell.
| **Admin Web Page**  	| web client  	|  anyone 	| Manual way to input data in the database. This is privilegied for users needing to add/amend/correct metadata related to subjects. For the local database, this is accessible here: http://localhost:8000/admin.
| **REST**  	|  web client 	|  anyone 	|   Programmatical way to input data, typically by acquisition software using a dedicated Alyx client [ONE](https://github.com/int-brain-lab/ONE) (Python) or [ALyx-matlab](https://github.com/cortex-lab/alyx-matlab) (Matlab).

For detailed information on using the Alyx admin Web interface, see [this Alyx usage guide](https://docs.google.com/document/d/1cx3XLZiZRh3lUzhhR_p65BggEqTKpXHUDkUDagvf9Kc/edit?usp=sharing).


### Create an experiment, register data and access it locally
Here we'll create the minimal set of fixtures to register some data to an experimental session.

1. create project
2. create repository
3. assign repository to lab
4. create a subject



If your server is not already running, from the root of the cloned repository:
```shell
source ./alyxvenv/bin/activate
python alyx/manage.py runserver
```

Then in another terminal:
```shell
source ./alyxvenv/bin/activate
pip install ONE-api
ipython
```
At the python prompt, this will create the set of init fixtures to register and recover data
```python
from pathlib import Path
from one.api import ONE

# create the local folder on the machine
one = ONE(base_url='http://localhost:8000')
ROOT_EXPERIMENTAL_FOLDER = Path.home().joinpath('alyx_local_data')
ROOT_EXPERIMENTAL_FOLDER.mkdir(parents=True, exist_ok=True)

# create the project
project = one.alyx.rest('projects', 'create', data=dict(name='main', users=['admin']))
# create the repository with name 'local' (NB: an URL is needed here, even if it is rubbish as below)
repo = one.alyx.rest('data-repository', 'create', data=dict(name='local', data_url='http://anyurl.org'))
# assign the repository to 'defaultlab'
one.alyx.rest('labs', 'partial_update', id='defaultlab', data=dict(repositories=['local']))
# create a subject
one.alyx.rest('subjects', 'create', data=dict(nickname='Algernon', lab='defaultlab', project='main', sex='M'))
```

#### Create a session using the REST endpoint and ONE-api
Activate your environment, install the ONE-api, and run a Python shell.
From the root of the repository:
```shell
source ./alyxvenv/bin/activate
pip install ONE-api
ipython
```
Then in Python
```python
# instantiate the one client
from pathlib import Path
import pandas as pd
import numpy as np
from one.api import ONE
from datetime import datetime
one = ONE(base_url='http://localhost:8000')
ROOT_EXPERIMENTAL_FOLDER = Path.home().joinpath('alyx_local_data')

# create a session
session_dict = dict(subject='Algernon', number=1, lab='defaultlab', task_protocol='test registration',
                    project="main", start_time=str(datetime.now()), users=['admin'])
session = one.alyx.rest('sessions', 'create', data=session_dict)
eid = session['url'][-36:]  # this is the experimental id that will be used to retrieve the data later

# create a trials table in the relative folder defaultlab/Subjects/Algernon/yyyy-mm-dd/001
session_path = ROOT_EXPERIMENTAL_FOLDER.joinpath(
    session['lab'], 'Subjects', session['subject'], session['start_time'][:10], str(session['number']).zfill(3))
alf_path = session_path.joinpath('alf')
alf_path.mkdir(parents=True, exist_ok=True)
ntrials = 400
trials = pd.DataFrame({'choice': np.random.randn(400) > 0.5, 'value': np.random.randn(400)})
trials.to_parquet(alf_path.joinpath('trials.table.pqt'))

# register the dataset
r = {'created_by': 'admin',
     'path': session_path.relative_to((session_path.parents[2])).as_posix(),
     'filenames': ['alf/trials.table.pqt'],
     'name': 'local'  # this is the repository name
     }
response = one.alyx.rest('register-file', 'create', data=r, no_cache=True)
```

#### Recover the data by querying the session
```python
from pathlib import Path
from one.api import ONE
one = ONE(base_url='http://localhost:8000')
ROOT_EXPERIMENTAL_FOLDER = Path.home().joinpath('alyx_local_data')
session =  one.alyx.rest('sessions', 'list', subject='Algernon')[-1]
eid = session['id']

# from the client side, provided with only the eids we reconstruct the full dataset paths
local_path = ROOT_EXPERIMENTAL_FOLDER.joinpath(*one.eid2path(eid).parts[-5:])
local_files = [local_path.joinpath(dset) for dset in one.list_datasets(eid)]
print(local_files)
```

We went straight to the point here, which was to create a session and register data, to go further consult the [One documentation](https://int-brain-lab.github.io/ONE/), in the section "Using one in Alyx".

## Backing up the database
See [this section](https://docs.google.com/document/d/1cx3XLZiZRh3lUzhhR_p65BggEqTKpXHUDkUDagvf9Kc/edit?tab=t.0#heading=h.dibimc48a9xl) in the Alyx user guide on how to back up and restore the database.  There are scripts in `alyx/scripts/templates/` for exporting the database to a sql file and importing from said file.

## Updating the database
The database should be updated each time there is a new Alyx release.  There is an update script in `alyx/scripts/auto-update.sh`, although you may need to change the source and cd command paths.

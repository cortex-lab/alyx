# Getting Started

Minimal working example of how to:
1. install a containerized version of Alyx + PostgreSQL
2. initialize it with the fixtures
3. register some local data to it
4. using the ONE-api, load the registered data

## Install a containerized version of Alyx + postgreSQL 

In this section we will start a fleet of two containers: one containing the alyx Django application 
and a web server, the other containing the database engine.

To start, make sure you have both `git` and `docker` installed in your system and clone the repository:

```shell
git clone https://github.com/cortex-lab/alyx.git
```

Copy the template configuration file from `environment_template.env` to `.env`
```shell
 cp alyx/alyx/alyx/environment_template.env alyx/alyx/alyx/.env
```
Update the `DJANGO_SECRET_KEY` value (you can create one on this website: [https://djecrety.ir/](https://djecrety.ir/))

Then we will start the containers. The `docker compose up` command will make sure the service is always running, even after a restart.

```shell
cd ./alyx/deploy
docker compose -f docker-compose-postgres-gunicorn.yaml up --detach 
```

Now this has started Alyx as a local service, with an empty database as a backend. So the very first time,
if we want connect to the application, we need to
- create the database empty table structure
- create a super user that will be the administrator
- load the "fixtures": this is the common set of database tables and record for all Alyx databases

```shell
# this commands checks that Django sees all working as intended
docker exec -it alyx_apache python manage.py check
# this commands will create the table structures on a new database, and do nothing otherwise
docker exec -it alyx_apache python manage.py migrate
# then load the fixtures: the set of tables common to all Alyx databases
docker exec -it alyx_apache /var/www/alyx/scripts/load-init-fixtures.sh
# at last create an administrator user
docker exec -it alyx_apache python manage.py createsuperuser
```

You can now visit the Alyx interface in your web browser at [http://localhost:8000](http://localhost:8000)

This is it ! In the next session, we will see how to register experiments and datasets on this database from a local python environment.


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


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
cp ./deploy/app/docker/settings-deploy.py alyx/alyx/settings.py
cp ./deploy/app/docker/settings_lab-deploy.py alyx/alyx/settings_lab.py
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
docker compose -f ./deploy/editable/docker-compose-postgres.yaml up -d
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

This repository is the single source of truth for both the production image and the base
compose file: the build context lives in `deploy/app/docker/` and the production compose in
`deploy/app/docker-compose.yaml`. Deployment orchestration (ansible, per-server compose
overrides, encrypted env) lives in the `iblsre` repository, not here.

We build our images on top of the apache2 images as it is the webserver we currently use.
Two images are produced: `internationalbrainlab/alyx_apache_base` (system + apache + venv)
and `internationalbrainlab/alyx_apache` (the base plus the alyx code).

### Standard release (CI/CD) — preferred, no manual build

1. Merge your changes to `master`.
2. Bump `__version__` in `alyx/alyx/__init__.py` and push to `master`.
3. On green CI, `.github/workflows/release.yml` cuts a git tag + GitHub release for the new
   version, then dispatches `.github/workflows/build-image.yml`.
4. `build-image.yml` builds both images locally, runs the ansible smoke test
   (`deploy/app/test/test-deploy-web.yaml`) against the freshly built image, and pushes both
   images tagged `<version>` and `latest` **only if the smoke test passes**.

Confirm the runs are green and the tags land on Docker Hub. A tag pushed manually (without a
version bump) also triggers `build-image.yml` directly.

### Manual build (fallback / hotfix)

```shell
# need to be in the build folder to copy some apache settings
cd ./deploy/app/docker/

# builds the base container
docker buildx build . \
  --platform linux/amd64 \
  --tag internationalbrainlab/alyx_apache_base:latest \
  -f ./Dockerfile_base

# builds the top layer (alyx_branch is the branch or tag to bake in)
docker buildx build . \
  --platform linux/amd64 \
  --tag internationalbrainlab/alyx_apache:latest \
  -f ./Dockerfile \
  --build-arg alyx_branch=master \
  --no-cache
```

## Advanced topics


### Single sign-on

Alyx can delegate login to an external identity provider through
[django-allauth](https://docs.allauth.org) - ORCID, Google, an institutional login, or any of
the providers allauth supports. It is optional and off by default.

```
pip install alyx[sso]
```

```python
# settings_lab.py
SSO_ENABLED = True
SSO_PROVIDER = 'orcid'          # any django-allauth provider id
SSO_PROVIDER_NAME = 'ORCID'     # the name on the sign-in button
SSO_CREATE_USER = True          # allow new identities to register (a public database)
SOCIALACCOUNT_PROVIDERS = {
    'orcid': {'APP': {'client_id': os.getenv('ORCID_CLIENT_ID'),
                      'secret': os.getenv('ORCID_CLIENT_SECRET')}},
}
```

Register `https://<your-host>/accounts/<provider>/login/callback/` as the redirect URI with the
provider. ORCID issues credentials from the developer tools in an ORCID account, and offers a
sandbox at `sandbox.orcid.org` for testing - point at it with
`'BASE_DOMAIN': 'sandbox.orcid.org'` in the provider settings.

Run `manage.py check` afterwards. It reports missing credentials and warns about combinations
that admit more people than you probably intend.

Identities are stored in allauth's own tables, keyed on `(provider, uid)` with a unique
constraint. **Those tables exist only where SSO is enabled** - migrations are per-app, so a
deployment that leaves `SSO_ENABLED` off never creates them.

#### Providers that supply no email address

This is the case ORCID presents, and it shapes the design. ORCID's OpenID Connect surface lists
neither `email` in its scopes nor `email_verified` in its claims: it returns the ORCID iD, a
name, and nothing else. An Alyx account created from such an identity therefore has **no email
address**, and that is a supported state - the account works for data access, it simply cannot
be emailed. The identity that matters is the `(provider, uid)` pair, not the address.

Consequently `SSO_ALLOWED_DOMAINS` cannot be used with such a provider: there is no domain to
match, and every sign-in would be refused.

| Setting | Default | |
| --- | --- | --- |
| `SSO_CREATE_USER` | `False` | Whether an identity with no account may create one. Off means SSO only signs in accounts that already exist, which is usually right for an internal database. |
| `SSO_ALLOWED_DOMAINS` | `()` | Restrict sign-in to these email domains. Unusable with a provider that supplies no email. |
| `SSO_NEW_USER_GROUPS` | `()` | Groups given to accounts SSO creates. On a public database the public users group is added automatically. |
| `SSO_ALLOW_SUPERUSER` | `False` | Whether a superuser may sign in through SSO. Superusers can change anything in the database, so they are worth keeping on credentials Alyx controls. |

#### API access for accounts without a password

An account created through SSO has no password, and Django will not give it one: password reset
skips users whose password is unusable, and the password change form requires the old password
they never had. Such a user therefore cannot obtain a token from `/auth-token`.

The **`/me` page** exists for this. Any signed-in user can see their REST API token there, copy
it into ONE, and regenerate it if it leaks:

```python
from one.api import ONE
ONE.setup(base_url='https://<your-host>', username='<username>', token='<token>')
```

The page is routed on every deployment, not just those using SSO, since it is the general
answer to "where do I get my API token".


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

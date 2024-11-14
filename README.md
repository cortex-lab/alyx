# alyx

[![Github Actions](https://github.com/cortex-lab/alyx/actions/workflows/main.yml/badge.svg)](https://github.com/cortex-lab/alyx/actions/)
[![Coverage Status](https://coveralls.io/repos/github/cortex-lab/alyx/badge.svg?branch=github_action)](https://coveralls.io/github/cortex-lab/alyx?branch=master)

Database for experimental neuroscience laboratories

Documentation: [Installation and getting started](http://alyx.readthedocs.io), [Alyx usage guide](https://docs.google.com/document/d/1cx3XLZiZRh3lUzhhR_p65BggEqTKpXHUDkUDagvf9Kc/edit?usp=sharing)


## Installation
Alyx has only been tested on Ubuntu (16.04 / 18.04 / 20.04), the latest is recommended. There are no guarantees that 
this setup will work on other systems. Assumptions made are that you have sudo permissions under an account named

[The getting started](docs/gettingstarted.md) section of the documentation details the steps for 
-   installing the Python/Django environment
-   serving a local database
-   registering local data
-   accessing local data using [ONE](https://one.internationalbrainlab.org)

## Contribution

* Development happens on the **dev** branch
* alyx is sync with the **master** branch
* alyx-dev is sync with the **dev** branch
* Migrations files are provided by the repository
* Continuous integration is setup, to run tests locally:
    - `./manage.py test -n` test without migrations (faster)
    - `./manage.py test` test with migrations (recommended if model changes)
    - NB: When running tests ensure `DEBUG = True` in the settings.py file (specifically `SECURE_SSL_REDIRECT = True` causes REST tests to fail)

```
$ /manage.py test -n
```

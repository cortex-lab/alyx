# alyx

[![Github Actions](https://github.com/cortex-lab/alyx/actions/workflows/main.yml/badge.svg)](https://github.com/cortex-lab/alyx/actions/)
[![Coverage Status](https://coveralls.io/repos/github/cortex-lab/alyx/badge.svg?branch=github_action)](https://coveralls.io/github/cortex-lab/alyx?branch=master)

Database for experimental neuroscience laboratories

[Documentation](https://cortex-lab.github.io/alyx/)

[Alyx Experimenter Guide](https://docs.google.com/document/d/1cx3XLZiZRh3lUzhhR_p65BggEqTKpXHUDkUDagvf9Kc/edit?usp=sharing)


## Installation

[The getting started](https://cortex-lab.github.io/alyx/00_gettingstarted.html) section of the documentation details the steps for 
-   installing the Python/Django environment
-   running the app with a development server
-   registering local data
-   accessing local data using [ONE](https://one.internationalbrainlab.org)

More complex deployments scenarios using web servers and Cloud applications are in the [how-to guides section of the documentation](docs/how-to-guides)

## Contribution

* Development happens on the **dev** branch
* alyx is in sync with the **master** branch
* alyx-dev is in sync with the **dev** branch
* Migration files are always provided by the repository

Contribution checklist:
- [ ] lint using ruff `ruff check .` at the root of the repository
- [ ] tests pass (see below how to run tests)
- [ ] migrations are provided with the commit
- [ ] update version number in `./alyx/alyx/__init__.py`
- [ ] update `CHANGELOG.md`


### Running tests

Continuous integration is setup. But before submitting a PR or commit,the tests can run locally.
    - `./manage.py test -n` test without migrations (faster)
    - `./manage.py test` test with migrations (recommended if model changes)

### Documentation contribution guide

#### Dependencies
```
pip install myst-parser sphinx_rtd_theme sphinx-autobuild
```

#### Build documentation locally

From the root of the repository.
````shell
sphinx-autobuild -b html ./docs/source ./docs/build/html --port 8700
````

# alyx

[![Github Actions](https://github.com/cortex-lab/alyx/actions/workflows/main.yml/badge.svg)](https://github.com/cortex-lab/alyx/actions/)
[![Coverage Status](https://coveralls.io/repos/github/cortex-lab/alyx/badge.svg?branch=github_action)](https://coveralls.io/github/cortex-lab/alyx?branch=master)

Database for experimental neuroscience laboratories

[Documentation](https://alyx.readthedocs.io)

[Alyx Experimenter Guide](https://docs.google.com/document/d/1cx3XLZiZRh3lUzhhR_p65BggEqTKpXHUDkUDagvf9Kc/edit?usp=sharing)


## Installation

[The getting started](https://alyx.readthedocs.io/en/latest/gettingstarted.html) section of the documentation details the steps for 
-   installing the Python/Django environment
-   running the app with a development server
-   registering local data
-   accessing local data using [ONE](https://one.internationalbrainlab.org)

More complex deployments scenarios using web servers and Cloud applications are in the [how-to guides section of the documtentaiton](docs/how-to-guides)

## Contribution

* Development happens on the **dev** branch
* alyx is sync with the **master** branch
* alyx-dev is sync with the **dev** branch
* Migrations files are always provided by the repository

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
sphinx-autobuild -b html ./docs ./docs/_build/ --port 8700
````

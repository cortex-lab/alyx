# alyx

[![Github Actions](https://github.com/cortex-lab/alyx/actions/workflows/main.yml/badge.svg)](https://github.com/cortex-lab/alyx/actions/)
[![Coverage Status](https://coveralls.io/repos/github/cortex-lab/alyx/badge.svg?branch=github_action)](https://coveralls.io/github/cortex-lab/alyx?branch=master)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21513696.svg)](https://doi.org/10.5281/zenodo.21513696)

Database for experimental neuroscience laboratories

[Documentation](https://cortex-lab.github.io/alyx/index.html)

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

Contribution checklist:
- [ ] lint using ruff `ruff check .` at the root of the repository
- [ ] tests pass (see below how to run tests)
- [ ] migrations are provided with the commit
- [ ] update version number in `./alyx/alyx/__init__.py`
- [ ] update `CHANGELOG.md`

Release process:
1. Open a PR from your feature branch into dev
2. On dev, bump the Alyx version and update the changelog
3. Open a PR from dev to master
4. When CI passes, make a squash commit into master using the version as the commit title, and changelog section as the message
5. Actions will automatically create a new release, deploy containers, and assign a DOI

### Running tests

Continuous integration is set up. But before submitting a PR or commit,the tests can run locally. First install the test dependencies with `pip install -r requirements_test.txt`.
    - `./manage.py test -n --parallel` parallel test without migrations (fastest)
    - `./manage.py test` test with migrations (recommended if models change)

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

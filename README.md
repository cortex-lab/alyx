# alyx

[![Build Status on master](https://travis-ci.org/cortex-lab/alyx.svg?branch=master)](https://travis-ci.org/cortex-lab/alyx)
[![Build Status on dev](https://travis-ci.org/cortex-lab/alyx.svg?branch=dev)](https://travis-ci.org/cortex-lab/alyx)

Database for experimental neuroscience laboratories

Documentation: http://alyx.readthedocs.io


## Development

* Development happens on the **dev** branch
* alyx is sync with the **master** branch
* alyx-dev is sync with the **dev** branch
* From now on, only main alyx should git add and push the migration files


## Deployment process

1. Freeze alyx-dev
2. Full test on alyx-dev
3. On Monday morning, merge dev to master
4. Update alyx to master
5. Make SQL migrations
6. Migrate
7. Git add and push the new migration files from alyx
8. Full test on alyx

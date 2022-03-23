

## Base container

The base container is the basic install with the current version of the repository. 
The following commands build the container and connect to it (only for testing it worked)

`TODO` install the apache packages here
```shell
docker build -t internationalbrainlab/alyx:base -f ./scripts/deployment_examples/docker-apache/Dockerfile.alyx.base .
docker run -it --rm internationalbrainlab/alyx:base 
```


## Alyx container

This container builds on top of the base one. Make sure that the following files exist and are the correct settings
 files for the alyx installation you are trying to build
```shell
./scripts/deployment_examples/docker-apache/settings.py
./scripts/deployment_examples/docker-apache/settings_secret.py
./scripts/deployment_examples/docker-apache/settings_lab.py
```
 Then run these commands
```shell
docker build -t internationalbrainlab/alyx:django -f ./scripts/deployment_examples/docker-apache/Dockerfile.alyx.django .
docker run -it --rm internationalbrainlab/alyx:django 
```

Generate the cache tables, in the container
```shell
./manage.py one_cache -v 2
```

On the host machine
```shell
docker container ls
docker cp e556eb550dc2:/backups/tables/* /datadisk/FlatIron/tables/one-cache
rsync -av --progress -e "ssh -i ~/.ssh/alyx.internationalbrainlab.org.pem" "/datadisk/FlatIron/tables/one-cache/tables/" ubuntu@alyx.internationalbrainlab.org:/var/www/alyx-main/tables
```

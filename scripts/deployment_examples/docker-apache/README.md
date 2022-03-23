

## Base container

The base container is the basic install with the current version of the repository.

`TODO` install the apache packages here
```shell
docker build -t internationalbrainlab/alyx:base -f ./scripts/deployment_examples/docker-apache/Dockerfile.alyx.base .
docker run -it --rm internationalbrainlab/alyx:django
```


## Alyx container

This container builds on top of the base one and adds the settings files located in 
`./scripts/deployments_examples/docker-apache`

`TODO` put the apache config files here
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

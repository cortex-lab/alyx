

## Base container

The base container is the basic install with the current version of the repository.

`TODO` install the apache packages here
```
docker build -t internationalbrainlab/alyx:base -f ./scripts/deployment_examples/docker-apache/Dockerfile.alyx.base .
docker run -it --rm -u $(id -u):$(id -g) internationalbrainlab/alyx:django
```


## Alyx container

This container builds on top of the base one and adds the settings files located in 
`./scripts/deployments_examples/docker-apache`

`TODO` put the apache config files here

```
docker build -t internationalbrainlab/alyx:django -f ./scripts/deployment_examples/docker-apache/Dockerfile.alyx.django .
docker run -it --rm internationalbrainlab/alyx:django
```

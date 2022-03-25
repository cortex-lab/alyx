## Useful docker commands 

To be run from within scripts/deployment_examples/alyx-docker
```shell
# Builds our webserver image with a tag 
sudo docker image build -t webserver_img .

# Builds our tagged image a webserver container
sudo docker run -i -t -d -p 80:80 -p 443:443 --name=webserver_con webserver_img

# Stops our container && removes container && removes any images that might be consuming vast amounts of storage 
sudo docker container stop -t 0 webserver_con && sudo docker container prune -f && sudo docker image prune -f

# Enters the bash shell of the running container
sudo docker exec -it webserver_con /bin/bash
```

## TODO
* evaluate wsgi errors that are present on both dockerized version of alyx and on prod alyx `/var/log/apache/error_alyx.log`
* RDS connection, PSQL install configs

## Base image

* to be reimplemented

## IBL Alyx image

This container builds on top of the base one. Make sure that the following files exist and are the correct settings
 files for the alyx installation you are trying to build
```shell
000-default-conf-<BUILD_ENV> (alyx-main, alyx-dev, local-alyx-dev, openalyx, etc)
```

Files intentionally not included in the repo, appropriate location has yet to be determined:
```
fullchain.pem (self signed for dev is ok)
privkey.pem (self signed for dev is ok)
ip-whitelist-conf
settings.py
settings_secret.py
settings_lab.py
```

### Notes on generate the cache tables

Open a bash shell in the container
```shell
sudo docker exec -it webserver_con /bin/bash
```

```shell
./manage.py one_cache -v 2
```

On the host machine
```shell
docker container ls
docker cp e556eb550dc2:/backups/tables/* /datadisk/FlatIron/tables/one-cache
rsync -av --progress -e "ssh -i ~/.ssh/alyx.internationalbrainlab.org.pem" "/datadisk/FlatIron/tables/one-cache/tables/" ubuntu@alyx.internationalbrainlab.org:/var/www/alyx-main/tables
```

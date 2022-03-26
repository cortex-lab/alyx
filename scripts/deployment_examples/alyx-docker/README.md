## TODO
* image is enormous, look for ways to reduce size
* find home for ibl alyx files (settings, configs)
* documentation

## Infrastructure steps (EC2, RDS, Gandi)
* placeholder

## Useful docker commands 

Post docker installation on ec2 instance; grant the ability to run docker commands without sudo:
```shell
# Add the docker group if it doesn't already exist:
sudo groupadd docker

# Add the connected user "$USER" to the docker group. Change the user name to match your preferred user if you do not 
# want to use your current user:
sudo gpasswd -a $USER docker

# Either log out/in to activate the changes to groups or run the following in your current session:
newgrp docker

# Test the permissions
docker run hello-world
```

---

To be run from within `scripts/deployment_examples/alyx-docker`
```shell
# Builds our webserver image with a tag 
docker image build --tag webserver_img .

# Builds our tagged image in a webserver container
docker run \
  --detach \
  --interactive \
  --tty \
  --publish 80:80 \
  --publish 443:443 \
  --publish 5432:5432 \
  --name=webserver_con webserver_img

# Enters the bash shell of the running container
docker exec --interactive --tty webserver_con /bin/bash

# Stops our container && removes container && removes any images that might be consuming vast amounts of storage 
docker container stop --time 0 webserver_con \
  && docker container prune --force \
  && docker image prune --force \
  && docker network prune --force
```

## IBL Alyx image

This container builds on top of the base one. Make sure that the following files exist and are the correct settings
 files for the alyx installation you are trying to build
```
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

## Base image

* to be reimplemented? required?

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

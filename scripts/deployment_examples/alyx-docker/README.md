## TODO
* image is enormous, look for ways to reduce size...ibllib...
* find home for ibl alyx files (settings, configs, certs)
* determine if using github actions to build and deploy container is feasible
  * https://github.com/iamamutt/IBL-pipeline/blob/master/.github/workflows/iblenv-docker-image.yml
  * https://github.com/iamamutt/IBL-pipeline/tree/master/docker

## Infrastructure (AWS, Gandi)
Steps involved to ensure the appropriate infrastructure is in place for running docker.

* Create EC2 instance
  * [AWS CLI Documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-services.html)
  * AWS Console interface
* (Optional) Assign Elastic IP address
* Create RDS instance for environment, populate db with appropriate data 
  * Verify the correct connection parameters are in settings_secret.py (intentionally not included in this repo)
* (Optional) Create IAM Role with appropriate RDS permissions and assign it to the EC2 instance
  * prod/dev requires read/write
  * openalyx requires just read (maybe?)
  * Not entirely useful as django needs connection info included anyway, but this does make testing db connections easier
* SSH into newly created EC2 instance and run the following (assuming Ubuntu 20.04)
```shell
# Set the hostname to something appropriate to your environment (alyx-prod, alyx-dev, openalyx, etc)
sudo hostnamectl set-hostname alyx-dev

# Update apt package index, install packages to allow apt to use a repository over HTTPS and git
sudo apt-get update
sudo apt-get install \
  ca-certificates \
  curl \
  git \
  gnupg \
  lsb-release

# Add Docker's official GPG key 
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# setup for Docker's stable repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Now that the correct repo is configured, update apt package index again, install docker
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io

# Verify Docker is installed
sudo docker run hello-world

# Perform any remaining package upgrades
sudo apt upgrade -y
```
* Restart the instance (Note that if an Elastic IP address is not being used, the IP will likely change)
* Create/update Gandi DNS entry for environment (alyx, alyx-dev, openalyx, etc)
  * Create either an `A record` with the `Public IPv4 address` or a `CNAME record` with the `Public IPv4 DNS`
  * Be sure to note the TTL (time to live) as this will give you a sense how quickly the DNS entry will become available
* Modify AWS security groups
  * Note that the security group assigned to the RDS instance will need the `Private IPv4 address` of the EC2 instance 
---
* Optional step to allow docker to run without sudo:
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

## Useful docker commands 

Commands to be run from within `.../scripts/deployment_examples/alyx-docker`
```shell
# Builds our webserver image with tag 
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

If you are trying to build the image, make sure that the following files exist in the same directory as the Dockerfile 
and are the correct settings files for the installation (db settings, servername, etc)
```
000-default-conf-<BUILD_ENV> (alyx-main, alyx-dev, local-alyx-dev, openalyx, etc)

-----

Files intentionally not included in the repo, appropriate location has yet to be determined:
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

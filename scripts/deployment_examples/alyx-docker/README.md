## TODO
* write instructions in the Alyx playbook
* automated docker build via github actions
---
Nice to haves:
* auto-deployment/auto-redeployment when a PR for master or dev is completed (there are a few different ways to tackle this)
* cleanup aws security groups (find better organization)
* auto update relevant aws security groups when deploying, utilize awscli
* auto update gandi DNS when deploying (gandi api - https://api.gandi.net/docs/livedns/)
* flesh out ibl_alyx_bootstrap.sh to handle more of the deployment/redeployment?

## Infrastructure (AWS, Gandi)
Steps involved to ensure the appropriate infrastructure is in place for running docker.

* Create EC2 instance from launch template
  * [AWS CLI Documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-services.html)
  * AWS Console interface
* (Optional) Assign Elastic IP address
* Create RDS instance for environment, populate db with appropriate data
  * Verify the correct connection parameters are in `settings_secret.py` (intentionally not included in this repo)
* (Optional) Create IAM Role with appropriate RDS and S3 permissions; assign it to the EC2 instance (this step is taken care of by the ec2 launch template)
  * prod/dev requires read/write to RDS
  * openalyx requires just read to RDS (maybe?)
  * S3 bucket just need read permissions
  * RDS permissions to the IAM Role is not completely necessary, but useful for troubleshooting
* SSH into newly created EC2 instance and run the following (assuming Ubuntu 20.04):
```shell
# Copy the ibl_alyx_bootstrap.sh file, or the contents of the file, to the home directory (assuming /home/ubuntu)
# Be sure to pass an argument for the environment (alyx-prod, alyx-dev, openalyx, etc)
sh ibl_alyx_bootstrap.sh alyx-dev
```
* Create/update Gandi DNS entry for environment (alyx, alyx-dev, openalyx, etc)
  * Create either an `A record` with the `Public IPv4 address` or a `CNAME record` with the `Public IPv4 DNS`
  * Be sure to note, or change, the TTL (time to live) as this will give you a sense how quickly the DNS entry will become available
* Modify AWS security groups
  * Note that the security group assigned to the RDS instance will need the `Private IPv4 address` of the EC2 instance
* You should now be able to access the instance via your browser, i.e. https://alyx-dev.internationalbrainlab.org
  * log in to ensure db connection is also working
  * navigate the site and attempt to break things
---
Below commands are in the `ibl_alyx_bootstrap.sh`, included here just for documentation purposes
```shell
# Set the hostname to something appropriate to your environment (alyx-prod, alyx-dev, openalyx, etc)
sudo hostnamectl set-hostname alyx-dev

# Update apt package index, install packages to allow apt to use a repository over HTTPS
sudo apt-get -qq update
sudo apt-get install -y \
  awscli \
  ca-certificates \
  curl \
  gnupg \
  lsb-release

# Add Docker's official GPG key 
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# setup for Docker's stable repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Now that the correct repo is configured; update apt package index again, install docker
sudo apt-get -qq update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io

# Verify Docker is installed
sudo docker run hello-world

# Download and configure cloudwatch logging (if relevant)
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
# modify the config if mistakes were made or just for more granular logging
sudo vim /opt/aws/amazon-cloudwatch-agent/bin/config.json
sudo mv /opt/aws/amazon-cloudwatch-agent/bin/config.json /home/ubuntu/alyx-docker/cloudwatch_config.json 
# start logging
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/home/ubuntu/alyx-docker/cloudwatch_config.json

# Perform any remaining package upgrades
sudo apt upgrade -y

# Restart the instance (Note that if an Elastic IP address is not being used, the IP will likely change)
sudo reboot
```

## Useful docker commands 

Cheat sheet of docker commands for troubleshooting
```shell
# Builds our webserver image with tag, specify the BUILD_ENV (alyx-prod, alyx-dev, openalyx, etc)
docker image build --build-arg BUILD_ENV=openalyx --tag webserver_img .

# Builds base image
docker build \
  --file Dockerfile.base \
  --tag internationalbrainlab/alyx:base .
# Builds IBL specific image, specify the BUILD_ENV (alyx-prod, alyx-dev, openalyx, etc)
docker build \
  --build-arg BUILD_ENV=alyx-dev \
  --file Dockerfile.ibl \
  --tag internationalbrainlab/alyx:ibl .

# Builds our tagged image in a webserver container
docker run \
  --detach \
  --interactive \
  --restart unless-stopped \
  --tty \
  --publish 80:80 \
  --publish 443:443 \
  --publish 5432:5432 \
  --name=alyx_con internationalbrainlab/alyx:ibl

# Enters the bash shell of the running container
docker exec --interactive --tty alyx_con /bin/bash

# To be performed when changing branches/troubleshooting
docker exec --interactive --tty alyx_con /bin/git -C /var/www/alyx status
docker exec --interactive --tty alyx_con /bin/git -C /var/www/alyx fetch
docker exec --interactive --tty alyx_con /bin/git -C /var/www/alyx checkout dev
docker exec --interactive --tty alyx_con /bin/git -C /var/www/alyx pull

# Below command is super dangerous, only included below for reference
docker exec --interactive --tty alyx_con /var/www/alyx/alyx/./manage.py makemigrations
docker exec --interactive --tty alyx_con /var/www/alyx/alyx/./manage.py migrate
# fixtures pulled from scripts/load-init-fixtures.sh (some files are excluded)
docker exec --interactive --tty alyx_con /var/www/alyx/alyx/./manage.py loaddata \
  /var/www/alyx/alyx/actions/fixtures/actions.proceduretype.json \
  /var/www/alyx/alyx/actions/fixtures/actions.watertype.json \
  /var/www/alyx/alyx/actions/fixtures/actions.cullreason.json \
  /var/www/alyx/alyx/data/fixtures/data.datarepositorytype.json \
  /var/www/alyx/alyx/data/fixtures/data.dataformat.json \
  /var/www/alyx/alyx/data/fixtures/data.datasettype.json \
  /var/www/alyx/alyx/misc/fixtures/misc.cagetype.json \
  /var/www/alyx/alyx/misc/fixtures/misc.enrichment.json \
  /var/www/alyx/alyx/misc/fixtures/misc.food.json \
  /var/www/alyx/alyx/subjects/fixtures/subjects.source.json \
  /var/www/alyx/alyx/experiments/fixtures/experiments.coordinatesystem.json \
  /var/www/alyx/alyx/experiments/fixtures/experiments.probemodel.json \
  /var/www/alyx/alyx/experiments/fixtures/experiments.brainregion.json

# Stops our container && removes container 
docker container stop --time 0 alyx_con
docker container prune --force

# Removes unused images && remove unused networks
docker image prune --force \
  && docker network prune --force

# Crontab entry to copy log files of the container (not good, but works)
*/5 * * * * docker cp alyx_con:/var/log/alyx.log /home/ubuntu/logs/ && docker cp alyx_con:/var/log/apache2/access_alyx.log /home/ubuntu/logs/ && docker cp alyx_con:/var/log/apache2/error_alyx.log /home/ubuntu/logs/ >/dev/null 2>&1
```
---
Give current user the ability to run Docker without sudo, if we want IP logging, we need to run Docker as root 
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

## Useful AWSCLI commands
Requires awscli be to installed and configured with the correct permissions on your development machine
```shell
# alyx-dev template
aws ec2 run-instances \
  --launch-template LaunchTemplateName=alyx-dev

ssh-keygen -f "/home/dirigibles/.ssh/known_hosts" -R "alyx-dev.internationalbrainlab.org"
```

## IBL Alyx image

If you are trying to build the image, make sure that the following files exist in the same directory as the Dockerfile 
and are the correct settings files for the installation (db settings, servername, etc)
```
000-default-conf-<BUILD_ENV> (alyx-prod, alyx-dev, openalyx, etc)

-----

Files intentionally not included in the repo, appropriate location has yet to be determined:
fullchain.pem (self-signed for dev is ok)
privkey.pem (self-signed for dev is ok)
ip-whitelist-conf
settings.py
settings_secret.py
settings_lab.py
```
---
Useful command for generating self-signed cert:
```shell
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout selfsigned.key -out selfsigned.crt

# To adhere to certbot conventions
mv selfsigned.key privkey.pem
mv selfsigned.crt fullchain.pem
```


## Base image

* to be reimplemented without apache configs

### Notes on generate the cache tables

Open a bash shell in the container
```shell
sudo docker exec -it alyx_con /bin/bash
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

#!/bin/sh

# TODO:
# * configure logging/cron jobs for logging (not great, but workable for now)
# * configure cron jobs for auto-deployment

# Set vars
WORKING_DIR=/home/ubuntu/alyx-docker

# check on arguments passed, at least one is required
if [ -z "$1" ]
  then
    echo "Error: No argument supplied, script requires first argument for build env (alyx-prod, alyx-dev, openalyx, etc)"
    exit 1
  else
    echo "Build environment argument supplied: $1"
fi

# check to make sure the script is being run as root (not ideal, Docker needs to run as root if we want IP logging)
if [ "$(id -u)" != "0" ]
  then
    echo "Script needs to be run as root, exiting."
    exit 1
fi

echo "Setting hostname of instance..."
hostnamectl set-hostname "$1"

echo "Update apt package index, install awscli, and allow apt to use a repository over HTTPS..."
apt-get -qq update
apt-get install -y \
  awscli \
  ca-certificates \
  curl \
  gnupg \
  lsb-release

echo "Add Docker's official GPG key, setup for the stable repo, update, and install packages"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get -qq update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io

echo "Testing docker..."
docker run hello-world

echo "Copying files from s3 bucket..." # this is dependant on the correct IAM role being applied to the EC2 instance
aws s3 cp s3://alyx-docker/000-default-conf-"$1" $WORKING_DIR
aws s3 cp s3://alyx-docker/apache-conf-"$1" $WORKING_DIR
aws s3 cp s3://alyx-docker/Dockerfile.ibl $WORKING_DIR
aws s3 cp s3://alyx-docker/fullchain.pem-"$1" $WORKING_DIR
aws s3 cp s3://alyx-docker/ip-whitelist-conf $WORKING_DIR
aws s3 cp s3://alyx-docker/privkey.pem-"$1" $WORKING_DIR
aws s3 cp s3://alyx-docker/settings.py-"$1" $WORKING_DIR
aws s3 cp s3://alyx-docker/settings_lab.py-"$1" $WORKING_DIR
aws s3 cp s3://alyx-docker/settings_secret.py-"$1" $WORKING_DIR
cd $WORKING_DIR || exit 1

echo "Building out docker image..."
docker build \
  --build-arg BUILD_ENV="$1" \
  --file Dockerfile.ibl \
  --tag internationalbrainlab/alyx:ibl .

echo "Building out docker container..."
docker run \
  --detach \
  --interactive \
  --restart unless-stopped \
  --tty \
  --publish 80:80 \
  --publish 443:443 \
  --publish 5432:5432 \
  --name=alyx_con internationalbrainlab/alyx:ibl

echo "Performing any remaining package upgrades..."
apt upgrade -y

echo "Instance needs to be reboot to ensure everything works correctly."
echo "NOTE: If an elastic IP address was not assigned, there is a possibility that the IP address will change."
while true; do
  echo "Reboot now? [y/n]"
  IFS= read -r yn
  case $yn in
    [Yy]* ) echo "Rebooting now..."; reboot;;
    [Nn]* ) echo "Exiting..."; exit;;
    * ) echo "Please answer [y]es or [n]o.";;
  esac
done

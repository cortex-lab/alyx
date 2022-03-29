#!/bin/sh

# TODO:
# * configure logging/cron jobs for logging (not great, but workable for now)
# * configure cron jobs for auto-deployment

# Set vars
WORKING_DIR=/home/ubuntu/alyx-docker

# check if an arg was passed, we require one arg
if [ -z "$1" ]
  then
    echo "Error: No argument supplied, script requires one argument for the build env (alyx-prod, alyx-dev, openalyx, etc)"
    exit 1
  else
    echo "Argument supplied: $1"
fi

# check to make sure the script is not being run as root
if [ "$(id -u)" -eq "0" ]
  then
    echo "Script should not be run as root, exiting."
    exit 1
fi

echo "Setting hostname of instance..."
sudo hostnamectl set-hostname "$1"

echo "Update apt package index and install packages to allow apt to use a repository over HTTPS..."
sudo apt-get update
sudo apt-get install \
  awscli \
  ca-certificates \
  curl \
  gnupg \
  lsb-release

echo "Add Docker's official GPG key.."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "Setup for Docker's stable repo..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "Now that the correct repo is configured; update apt package index again, install docker..."
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io -y

echo "Adding the docker group if it doesn't already exist..."
sudo groupadd docker

echo "Adding the connected user to the docker group..."
sudo gpasswd -a "$USER" docker

echo "Activating the changes to groups in current session..."
newgrp docker

echo "Testing docker permissions..."
docker run hello-world

echo "Copying files from s3 bucket..." # this is dependant on the correct IAM role being applied to the EC2 instance
aws s3 cp s3://alyx-docker $WORKING_DIR --recursive
cd $WORKING_DIR || exit 1

echo "Building out docker image..."
docker image build --build-arg BUILD_ENV="$1" --tag webserver_img .

echo "Building out docker container..."
docker run \
  --detach \
  --interactive \
  --restart unless-stopped \
  --tty \
  --publish 80:80 \
  --publish 443:443 \
  --publish 5432:5432 \
  --name=webserver_con webserver_img

echo "Performing any remaining package upgrades..."
sudo apt upgrade -y

echo "Instance needs to be reboot to ensure everything works correctly."
echo "NOTE: If an elastic IP address was not assigned, there is a possibility that the IP address will change."
while true; do
  echo "Reboot now? [y/n]"
  IFS= read -r yn
  case $yn in
    [Yy]* ) echo "Rebooting now..."; sudo reboot;;
    [Nn]* ) echo "Exiting..."; exit;;
    * ) echo "Please answer [y]es or [n]o.";;
  esac
done

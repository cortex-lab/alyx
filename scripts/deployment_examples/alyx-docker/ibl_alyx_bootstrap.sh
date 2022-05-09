#!/bin/bash

# Once this script is in the desired directory of a newly created instance, a sample command to run:
# sudo sh ibl_alyx_bootstrap.sh alyx-dev

echo "NOTE: Installation log can be found in the directory the script is called from and named 'ibl_alyx_bootstrap_install.log'"
{
# check to make sure the script is being run as root (not ideal, Docker needs to run as root for IP logging)
if [ "$(id -u)" != "0" ]; then
  echo "Script needs to be run as root, exiting."
  exit 1
fi

# check on arguments passed, at least one is required to pick build env
if [ -z "$1" ]; then
    echo "Error: No argument supplied, script requires first argument for build env (alyx-prod, alyx-dev, openalyx, etc)"
    exit 1
  else
    echo "Build environment argument supplied: $1"
fi

# Set vars
WORKING_DIR=/home/ubuntu/alyx-docker
LOG_DIR=/home/ubuntu/logs
EC2_REGION="eu-west-2"
IP_ADDRESS=$(ip route get 8.8.8.8 | awk -F"src " 'NR==1{split($2,a," ");print a[1]}')
DATE_TIME=$(date +"%Y-%m-%d %T")
SG_DESCRIPTION="${1}, ec2 instance, created: ${DATE_TIME}"
LOG_CRON="*/5 * * * * docker cp alyx_con:/var/log/alyx.log ${LOG_DIR} && docker cp alyx_con:/var/log/apache2/access_alyx.log ${LOG_DIR} && docker cp alyx_con:/var/log/apache2/error_alyx.log ${LOG_DIR} >/dev/null 2>&1"
CERTBOT_CRON="30 1 1,15 * * docker exec alyx_con /bin/bash /home/ubuntu/iblalyx/crons/renew_docker_certs.sh ${1} > ${LOG_DIR}/cert_renew.log 2>&1"

echo "Creating relevant directories and log files..."
mkdir -p $WORKING_DIR
mkdir -p $LOG_DIR
touch "${LOG_DIR}/cert_renew.log"
chmod 666 "${LOG_DIR}/cert_renew.log"

echo "Setting hostname of instance..."
hostnamectl set-hostname "$1"

echo "Setting timezone to Europe\Lisbon..."
timedatectl set-timezone Europe/Lisbon

echo "Add Docker's official GPG key, setup for the docker stable repo"
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "Update apt package index, install awscli docker, and allow apt to use a repository over HTTPS..."
apt-get -qq update
apt-get install -y \
  awscli \
  ca-certificates \
  containerd.io \
  docker-ce \
  docker-ce-cli \
  gnupg

echo "Testing docker..."
docker run hello-world

echo "Adding IP Address to 'alyx_rds' security group with unique description..."
aws ec2 authorize-security-group-ingress \
    --region=$EC2_REGION \
    --group-name alyx_rds \
    --ip-permissions IpProtocol=tcp,FromPort=5432,ToPort=5432,IpRanges="[{CidrIp=${IP_ADDRESS}/32,Description='${SG_DESCRIPTION}'}]"

echo "Copying files from s3 bucket..." # this is dependant on the correct IAM role being applied to the EC2 instance
cd $WORKING_DIR || exit 1
aws s3 cp s3://alyx-docker/000-default-conf-"$1" .
aws s3 cp s3://alyx-docker/apache-conf-"$1" .
aws s3 cp s3://alyx-docker/Dockerfile.ibl .
aws s3 cp s3://alyx-docker/fullchain.pem-"$1" .
aws s3 cp s3://alyx-docker/ip-whitelist-conf .
aws s3 cp s3://alyx-docker/privkey.pem-"$1" .
aws s3 cp s3://alyx-docker/settings.py-"$1" .
aws s3 cp s3://alyx-docker/settings_lab.py-"$1" .
aws s3 cp s3://alyx-docker/settings_secret.py-"$1" .
aws s3 cp s3://alyx-docker/cloudwatch_config.json-"$1" .

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

echo "Building out crontab entries..."
echo -e "${LOG_CRON}\n${CERTBOT_CRON}" >> temp_cron
crontab temp_cron # install new cron file
rm temp_cron # remove temp_cron file

echo "Download and configure cloudwatch logging..."
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i -E ./amazon-cloudwatch-agent.deb
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/home/ubuntu/alyx-docker/cloudwatch_config.json-"$1"

echo "Adding alias to .bashrc..."
echo '' >> /home/ubuntu/.bashrc \
  && echo "# IBL Alias" >> /home/ubuntu/.bashrc \
  && echo "alias docker-bash='sudo docker exec --interactive --tty alyx_con /bin/bash'" >> /home/ubuntu/.bashrc

echo "Performing any remaining package upgrades..."
apt upgrade -y

echo "Instance will now reboot to ensure everything works correctly on a fresh boot."
sleep 10s
} | tee -a ibl_alyx_bootstrap_install.log

reboot

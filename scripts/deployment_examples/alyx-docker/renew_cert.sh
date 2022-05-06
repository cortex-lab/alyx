#!/bin/bash
# A script to renew let's encrypt certificates from within a restricted AWS EC2 instance
# $1 - security group to add, e.g. sg-0e21a23cf76d78537
# $2 - instance ID, e.g. i-0eb9d0f10dcd87365 (optional if running from instance)

EC2_INSTANCE_ID=$2
EC2_REGION="eu-west-2"
PROFILE=certbot
# If not instance ID provided, assume we're running from within one and fetch the ID
if [ -z $EC2_INSTANCE_ID ]
then
  die() { status=$1; shift; echo "FATAL: $*"; exit $status; }
  EC2_INSTANCE_ID="`wget -q -O - http://169.254.169.254/latest/meta-data/instance-id || die "wget instance-id has failed: $?\"`"
fi

# Get a list of security groups attached to this instance
sg_groups=$(aws ec2 describe-instances --instance-id $EC2_INSTANCE_ID --query "Reservations[].Instances[].SecurityGroups[].GroupId[]" --output text --profile $PROFILE)

# Check if $1 is in group list, if not add
in_list=0
case $sg_groups in *"$1"*) in_list=1 ;; esac

to_attach=$sg_groups
if [ $in_list -eq 0 ]
then
  echo "Attaching group $1 to instance $EC2_INSTANCE_ID"
  to_attach+=" $1"
  aws --region $EC2_REGION ec2 modify-instance-attribute --instance-id $EC2_INSTANCE_ID --groups $to_attach --profile $PROFILE
fi

# Renew certs
echo "Renewing certs"
sudo certbot -q renew  || echo "Failed to renew certs"

# Reset
if [ $in_list -eq 0 ]
then
  echo "Resetting security groups for $EC2_INSTANCE_ID"
  aws --region $EC2_REGION ec2 modify-instance-attribute --instance-id $EC2_INSTANCE_ID --groups $sg_groups --profile $PROFILE
fi

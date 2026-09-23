#!/bin/bash
set -e
# A script to add or remove a security group rule for EC2 instances.
# This is intended to ask as a pre- and post-hook for certbot renewal in restricted AWS EC2 instances.
# --hostname/-h determines the environment (alyx-prod, alyx-dev, openalyx, or full domain name)
# --security-group/-s is the security group ID for certbot renewal (default is sg-07b6343c0d485e097)
# --region/-r is the AWS region (default is eu-west-2)
# --add or --remove to specify the action to perform (default is "add")
# --dry-run/-d performs all checks without modifying the instance

# Parse command line arguments
ACTION="add"
HOSTNAME=""
SECURITY_GROUP=""
REGION=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--hostname)
      HOSTNAME="$2"
      shift 2
      ;;
    -s|--security-group)
      SECURITY_GROUP="$2"
      shift 2
      ;;
    -r|--region)
      REGION="$2"
      shift 2
      ;;
    --add)
      ACTION="add"
      shift
      ;;
    --remove)
      ACTION="remove"
      shift
      ;;
    -d|--dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--hostname|-h <hostname>] [--security-group|-s <sg-id>] [--region|-r <region>] [--add|--remove] [--dry-run|-d]"
      exit 1
      ;;
  esac
done

# Set Vars with defaults and environment variable fallbacks
if [ -z "$SECURITY_GROUP" ]; then
  if [ -z "$CERTBOT_SG" ]; then
    CERTBOT_SG="sg-07b6343c0d485e097"
  else
    CERTBOT_SG="$CERTBOT_SG"
  fi
else
  CERTBOT_SG="$SECURITY_GROUP"
fi

EC2_REGION=${REGION:-${3:-eu-west-2}}

echo "Checking arg passed for build environment..."
if [ "${HOSTNAME}" == "alyx-dev" ]; then
  ALYX_HOSTNAME="dev.alyx.internationalbrainlab.org"
elif [ "${HOSTNAME}" == "alyx-prod" ]; then
  ALYX_HOSTNAME="alyx.internationalbrainlab.org"
elif [ "${HOSTNAME}" == "openalyx" ]; then
  ALYX_HOSTNAME="openalyx.internationalbrainlab.org"
elif [ -z "$HOSTNAME" ]; then
  if [ -z "$APACHE_SERVER_NAME" ]; then
    echo "Error: No hostname supplied and no APACHE_SERVER_NAME set, please set one of them."
    exit 1
  else
    ALYX_HOSTNAME="${APACHE_SERVER_NAME}"
  fi
else
  ALYX_HOSTNAME="${HOSTNAME}"
fi
echo "ALYX_HOSTNAME set to ${ALYX_HOSTNAME}"

if [ -z "$EC2_INSTANCE_ID" ];
then
  echo "Retrieving instance-id from local metadata..."
  # Try using cloud utils (NB: this may not work within a docker container and is not installed by default)
  EC2_INSTANCE_ID=$(ec2metadata --instance-id)
  if [ -z "$EC2_INSTANCE_ID" ]; then
    echo "Error: Unable to retrieve EC2 instance ID from metadata service."
    exit 1
  fi
  echo "Using EC2_INSTANCE_ID from metadata service: ${EC2_INSTANCE_ID}"
else
  echo "Using EC2_INSTANCE_ID from environment: ${EC2_INSTANCE_ID}"
fi

# If APACHE_SERVER_ADMIN is set, use it; otherwise, default to admin@domain
if [ -z "$APACHE_SERVER_ADMIN" ]; then
    domain=$(echo "$ALYX_HOSTNAME" | awk -F. '{print $(NF-1)"."$NF}')
    email="admin@$domain"
else
    email="$APACHE_SERVER_ADMIN"
fi


echo "Retrieving list of security groups attached to this instance..."
SG_IDS=$(aws ec2 describe-instances \
  --region=$EC2_REGION \
  --instance-id $EC2_INSTANCE_ID \
  --query "Reservations[].Instances[].SecurityGroups[].GroupId[]" \
  --output text)
echo "SG_IDS found: ${SG_IDS}"
# check if the "certbot_renewal" security group is in SG_IDS list
in_list=0
case $SG_IDS in *$CERTBOT_SG*) in_list=1 ;; esac

if [ "$ACTION" == "add" ]; then
  if [ $in_list -eq 0 ]; then
    echo "Attaching the security group ${CERTBOT_SG} to the instance..."
    sg_ids="${SG_IDS} ${CERTBOT_SG}"
  else
    echo "Security group ${CERTBOT_SG} is already attached to the instance."
    exit 0
  fi
elif [ "$ACTION" == "remove" ]; then
  if [ $in_list -eq 1 ]; then
    echo "Removing the security group ${CERTBOT_SG} from the instance..."
    # Remove CERTBOT_SG from SG_IDS
    sg_ids=$(echo $SG_IDS | tr ' ' '\n' | grep -v "$CERTBOT_SG" | tr '\n' ' ')
  else
    echo "Security group ${CERTBOT_SG} is not attached to the instance."
    exit 0
  fi
else
  echo "Unknown action: $ACTION. Use 'add' or 'remove'."
  exit 1
fi

if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Would execute:"
  echo "aws ec2 modify-instance-attribute --region $EC2_REGION --instance-id $EC2_INSTANCE_ID --groups $sg_ids"
  echo "[DRY RUN] Action '$ACTION' would be completed."
else
  aws ec2 modify-instance-attribute \
      --region $EC2_REGION \
      --instance-id $EC2_INSTANCE_ID \
      --groups $sg_ids

  echo "Action '$ACTION' completed."
fi

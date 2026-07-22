#!/bin/bash
set -e
# This script is used to create a new SSL certificate for the Alyx server if certificates do not exist
# $APACHE_SERVER_NAME is the hostname, e.g. example.com, sub.example.com, or localhost

if [ "$APACHE_SERVER_NAME" = "localhost" ]; then
    echo "Deactivating SSL module for localhost."
    # Command to deactivate SSL module
    a2dismod ssl
    echo "Skipping certificate generation for localhost."
    # Ensure changes are applied
    exit 0
fi


echo "Enabling SSL module for $APACHE_SERVER_NAME."
# Command to enable SSL module
a2enmod ssl
echo "SSL module enabled for $APACHE_SERVER_NAME."
# First check if the certificate files exist
if [ ! -f /etc/letsencrypt/live/$APACHE_SERVER_NAME/fullchain.pem ] || [ ! -f /etc/letsencrypt/live/$APACHE_SERVER_NAME/privkey.pem ]; then
    echo "SSL certificate files do not exist. Proceeding with certificate generation"
    # To get apache running for the certbot challenge we first create a temporary self-signed certificate
    echo "Generating self-signed SSL certificate for $APACHE_SERVER_NAME"
    # Create directories if they do not exist
    mkdir -p /etc/letsencrypt/live/$APACHE_SERVER_NAME
    openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
        -keyout /etc/letsencrypt/live/$APACHE_SERVER_NAME/privkey.pem \
        -out /etc/letsencrypt/live/$APACHE_SERVER_NAME/fullchain.pem \
        -subj "/C=GB/ST=London/L=London/O=IBL/OU=IT/CN=${APACHE_SERVER_NAME}" &&

    echo "Attempting to issue certificates for $APACHE_SERVER_NAME"
    # Start apache server with self-signed certificates (in background)
    apache2ctl start
    sleep 2  # wait for apache to start
    # Remove self-signed certificates before generating LetsEncrypt ones
    rm -rf /etc/letsencrypt/live/$APACHE_SERVER_NAME
    # Generate a new SSL certificate using certbot
    if [ -n "$CERTBOT_SG" ]; then  # call script to temporarily remove firewall for certbot challange
	    certbot certonly --webroot --webroot-path=/var/www/alyx --noninteractive --agree-tos --email $APACHE_SERVER_ADMIN -d $APACHE_SERVER_NAME --pre-hook '/home/iblalyx/crons/ec2_modify_groups.sh --add' --post-hook '/home/iblalyx/crons/ec2_modify_groups.sh --remove'
    else
        certbot certonly --webroot --webroot-path=/var/www/alyx --noninteractive --agree-tos --email $APACHE_SERVER_ADMIN -d $APACHE_SERVER_NAME
    fi

    # Stop apache server (will be started by docker-compose with -DFOREGROUND)
    apache2ctl stop

fi
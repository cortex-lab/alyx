
# Apache Site Configuration

If the database needs to be served on the web, one tested solution is to use an apache web server.

## Install apache, wsgi module, and set group and acl permissions
```shell
sudo apt-get update    
sudo apt-get install apache2 libapache2-mod-wsgi-py3 acl
sudo a2enmod wsgi
sudo adduser www-data syslog
sudo adduser ubuntu syslog
sudo setfacl -d -m u:www-data:rwx /var/log/
sudo setfacl -d -m u:ubuntu:rwx /var/log/
```

Put the [site configuration](_static/001-alyx.conf) here: `/etc/apache2/sites-available/001-alyx.conf`
-   make sure the paths within the file match the alyx installation path.
-   update ServerName parameter `ServerName  alyx.internationalbrainlab.org`
-   it should match the `alyx/alyx/settings_lab.py` `ALLOWED_HOSTS` parameter


Activate the website

    sudo a2ensite
        001-alyx-main

Restart the server, 2 commands are provided here for reference. Reload is recommended on a running production server as 
it should not interrupt current user transactions if any.


    sudo /etc/init.d/apache2 restart
    sudo /etc/init.d/apache2 reload


Location of error logs for apache if it fails to start

    /var/log/apache2/

## [Optional] Setup AWS Cloudwatch Agent logging

If you are running alyx as an EC2 instance on AWS, you can easily add the AWS Cloudwatch agent to the server to ease log
evaluation and alerting. This can also be done with a non-ec2 server, but is likely not worth it unless you are already 
using Cloudwatch for other logs.

To give an overview of the installation process for an EC2 instance:
* Create an IAM role that enables the agent to collect metrics from the server and attach the role to the server.
* Download the agent package to the instance.
* Modify the CloudWatch agent configuration file, specify the metrics and the log files that you want to collect.
* Install and start the agent on your server.
* Verify in Cloudwatch 
  * you are now able to generate alerts from the metrics of interest
  * you are now shipping the logs files to your log group

Follow the latest instructions from the official [AWS Cloudwatch Agent documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Install-CloudWatch-Agent.html).

Other useful references:
* [IAM documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-vs-inline.html)
* [EC2 metadata documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-metadata.html) 

---

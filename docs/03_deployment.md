
# Deployments how-to's guides

If the database needs to be served on the web, one tested solution is to use an apache web server.



## Advanced topics

### Building the docker containers

We have built our images on top of the apache2 images as it is the webserver we currently use. 
However as shown in the getting started section, those images are suitable for use with different servers such as gunicorn.

```shell
# need to be in the build folder to copy some apache settings
cd ./alyx/deploy/docker/

# builds the base container
docker buildx build . \
  --platform linux/amd64 \
  --tag internationalbrainlab/alyx_apache_base:latest \
  -f ./Dockerfile_base

# builds the top layer
docker buildx build . \
  --platform linux/amd64 \
  --tag internationalbrainlab/alyx_apache:latest \
  -f ./Dockerfile \
  --build-arg alyx_branch=deploy \
  --no-cache
```

```shell
docker image push internationalbrainlab/alyx_apache_base:latest
docker image push internationalbrainlab/alyx_apache:latest
```

### Apache webserver and interaction with wsgi

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

---

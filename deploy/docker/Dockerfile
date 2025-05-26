FROM internationalbrainlab/alyx_apache_base:latest

COPY settings-deploy.py /var/www/alyx/alyx/alyx/settings.py
COPY settings_lab-deploy.py /var/www/alyx/alyx/alyx/settings_lab.py

RUN git -C /var/www/alyx pull
RUN git -C /home/iblalyx pull
RUN git -C /home/iblalyx checkout -b deploy

WORKDIR /var/www/alyx/alyx

# the entrypoint here just starts a local development server, this is overriden by the compose file
CMD python /var/www/alyx/alyx/manage.py collectstatic --noinput && python /var/www/alyx/alyx/manage.py runserver 0.0.0.0:8000

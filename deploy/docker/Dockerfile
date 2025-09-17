FROM internationalbrainlab/alyx_apache_base:latest

COPY settings-deploy.py /var/www/alyx/alyx/alyx/settings.py
COPY settings_lab-deploy.py /var/www/alyx/alyx/alyx/settings_lab.py
COPY settings_lab-user.py* /var/www/alyx/alyx/alyx/settings_lab.py

ARG alyx_branch=deploy

RUN git -C /var/www/alyx fetch origin ${alyx_branch}
RUN git -C /var/www/alyx checkout -B ${alyx_branch} origin/${alyx_branch}
RUN git -C /home/iblalyx fetch origin ${alyx_branch}
RUN git -C /home/iblalyx checkout -B ${alyx_branch} origin/${alyx_branch}

RUN pip install -r /var/www/alyx/requirements.txt

WORKDIR /var/www/alyx/alyx

# the entrypoint here just starts a local development server, this is overriden by the compose file in production
CMD python /var/www/alyx/alyx/manage.py collectstatic --noinput && python /var/www/alyx/alyx/manage.py runserver 0.0.0.0:8000

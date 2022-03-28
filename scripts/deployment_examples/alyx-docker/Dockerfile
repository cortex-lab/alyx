FROM ubuntu

# Set build environtment, passed from command line --build-arg (alyx-prod, alyx-dev, openalyx, etc)
ARG BUILD_ENV

# Apache ENVs
ENV APACHE_RUN_USER www-data
ENV APACHE_RUN_GROUP www-data
ENV APACHE_LOCK_DIR /var/lock/apache2
ENV APACHE_LOG_DIR /var/log/apache2
ENV APACHE_PID_FILE /var/run/apache2/apache2.pid
ENV APACHE_SERVER_NAME ${BUILD_ENV}.internationalbrainlab.org

# Time zone autoconfig
ENV TZ=Europe/Lisbon
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install services, packages and do cleanup
RUN apt-get update && apt-get install -y \
    apache2 \
    apache2-utils \
    git \
    libapache2-mod-wsgi-py3 \
    postgresql \
    python3.8 \
    python3-pip \
    python3-venv \
    virtualenv \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*
 
# Apache configs
COPY apache-conf                   /etc/apache2/apache2.conf
COPY 000-default-conf-${BUILD_ENV} /etc/apache2/sites-available/000-default.conf
COPY ip-whitelist-conf             /etc/apache2/sites-available/ip_whitelist.conf
COPY fullchain.pem                 /etc/apache2/ssl/fullchain.pem
COPY privkey.pem                   /etc/apache2/ssl/privkey.pem
RUN echo "ServerName ${BUILD_ENV}.internationalbrainlab.org" >> /etc/apache2/apache2.conf

# Clone repos, configure virtual environment, and make our image massive
RUN git clone --depth 1 --single-branch --branch master https://github.com/cortex-lab/alyx.git /var/www/${BUILD_ENV}
RUN git clone --depth 1 --single-branch --branch main https://github.com/int-brain-lab/iblalyx.git /var/www/${BUILD_ENV}/ibl-alyx
WORKDIR /var/www/${BUILD_ENV}
# Best practice for configuring python venv
ENV VIRTUAL_ENV=/var/www/${BUILD_ENV}/venv
RUN virtualenv ${VIRTUAL_ENV} --python=python3
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install -r requirements.txt
RUN pip install ONE-api

# Alyx configs
COPY settings.py-${BUILD_ENV}        /var/www/${BUILD_ENV}/alyx/alyx/settings.py
COPY settings_secret.py-${BUILD_ENV} /var/www/${BUILD_ENV}/alyx/alyx/settings_secret.py
COPY settings_lab.py-${BUILD_ENV}    /var/www/${BUILD_ENV}/alyx/alyx/settings_lab.py
RUN touch /var/log/alyx.log \
    && chown www-data:www-data /var/log/alyx.log \
    && chmod 755 /var/log/alyx.log

# Expose ports, enable apache modules, and launch apache
EXPOSE 80 443 5432
RUN a2enmod rewrite
RUN a2enmod ssl
RUN a2enmod wsgi
CMD ["/usr/sbin/apache2ctl", "-DFOREGROUND"]
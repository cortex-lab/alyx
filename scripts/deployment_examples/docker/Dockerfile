
FROM postgres:13.1

# note - pg_ctl & datadir as follows:
# /usr/lib/postgresql/9.6/bin/pg_ctl -D /var/lib/postgresql/data 

RUN apt-get update && \
	apt-get install -y git python3-pip nvi \
	&& pip3 install --upgrade pip

RUN cd / \
	&& git clone https://github.com/cortex-lab/alyx.git \
	&& cd alyx && pip3 install -r requirements.txt

EXPOSE 8000/tcp
COPY alyx-entrypoint.sh /
ENTRYPOINT ["/alyx-entrypoint.sh" ]

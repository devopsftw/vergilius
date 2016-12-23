FROM phusion/baseimage
MAINTAINER Vasiliy Ostanin <bazilio91@gmail.ru>

RUN add-apt-repository ppa:nginx/development
RUN apt-get update
#apt-get upgrade -y -o Dpkg::Options::="--force-confold" && \
RUN apt-get install -y ca-certificates nginx git-core python3 build-essential autoconf libtool \
    python3-dev libffi-dev libssl-dev python3-pip dialog nano
ENV TERM screen

COPY docker/init.d/01_env.sh /etc/init.d/
COPY docker/services/nginx.sh /etc/service/nginx/run
COPY docker/services/vergilius.sh /etc/service/vergilius/run

COPY docker/consul/* /etc/consul/conf.d/
COPY docker/nginx/conf.d/*.conf /etc/nginx/conf.d/
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
RUN rm /etc/nginx/sites-enabled/* && mkdir -p /etc/nginx/sites-enabled/certs && \
    mkdir -p /data/dummy_ca/domains/

COPY src /opt/vergilius
RUN cd /opt/vergilius/ && python3 setup.py install
WORKDIR /opt/vergilius/

EXPOSE 80 443

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

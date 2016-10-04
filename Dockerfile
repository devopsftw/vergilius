FROM phusion/baseimage
MAINTAINER Vasiliy Ostanin <bazilio91@gmail.ru>

RUN add-apt-repository ppa:nginx/development
RUN apt-get update
#apt-get upgrade -y -o Dpkg::Options::="--force-confold" && \
RUN apt-get install -y ca-certificates nginx git-core python build-essential autoconf libtool \
    python-dev libffi-dev libssl-dev python-pip dialog nano
ENV TERM screen

ADD init.d/01_env.sh /etc/init.d/
ADD services/nginx.sh /etc/service/nginx/run
ADD services/vergilius.sh /etc/service/vergilius/run

COPY consul/* /etc/consul/conf.d/
COPY nginx/conf.d/*.conf /etc/nginx/conf.d/
COPY nginx/nginx.conf /etc/nginx/nginx.conf
RUN rm /etc/nginx/sites-enabled/* && mkdir -p /etc/nginx/sites-enabled/certs && \
    mkdir -p /data/dummy_ca/domains/

ADD src /opt/vergilius
RUN cd /opt/vergilius/ && python setup.py install
WORKDIR /opt/vergilius/

EXPOSE 80 443 7000-8000

ENV DHPARAM_LENGTH 4096

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

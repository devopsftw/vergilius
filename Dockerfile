FROM phusion/passenger-full
MAINTAINER Vasiliy Ostanin <bazilio91@gamil.ru>

RUN apt-key adv --keyserver hkp://pgp.mit.edu:80 --recv-keys 573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62
RUN echo "deb http://nginx.org/packages/mainline/ubuntu/ trusty nginx" > /etc/apt/sources.list.d/nginx.list

ENV NGINX_VERSION 1.9.9-1~trusty

RUN apt-get update
RUN apt-get upgrade -y -o Dpkg::Options::="--force-confold" \
    apt-get install -y ca-certificates nginx=${NGINX_VERSION} git-core python build-essential autoconf libtool \
    python-dev libffi-dev libssl-dev python-pip dialog

RUN git clone https://github.com/letsencrypt/letsencrypt /opt/letsencrypt
RUN curl https://bootstrap.pypa.io/ez_setup.py -o - | python

#RUN git clone https://github.com/movableink/doorman.git /var/doorman
#RUN cd /var/doorman && npm install
#COPY doorman/* /var/doorman/

ADD init.d/01_env.sh /etc/init.d/
ADD services/nginx.sh /etc/service/nginx/run

COPY consul/* /etc/consul/conf.d/
COPY letsencrypt.sh /etc/
COPY nginx/conf.d/*.conf /etc/nginx/conf.d/
COPY nginx/nginx.conf /etc/nginx/nginx.conf
RUN mkdir -p /etc/nginx/sites-enabled/certs

COPY vergilius /opt/vergilius
RUN pip install -U letsencrypt
RUN pip install -e /opt/vergilius

EXPOSE 80 443

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
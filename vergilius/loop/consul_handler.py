import os
from subprocess import call

import consul
from consul import tornado, base
from tornado.locks import Event

import config
from loop.service import Service


class ConsulHandler(object):
    nginx_update_event = Event()
    tc = tornado.Consul(host=config.CONSUL_HOST)
    c = consul.Consul(host=config.CONSUL_HOST)

    def __init__(self):
        self.services = {}

        self.data = {}
        self.modified = False
        self.watch_services()
        self.nginx_reload()

    @tornado.gen.coroutine
    def watch_services(self):
        index = None
        while True:
            try:
                index, data = yield self.tc.catalog.services(index, wait=None)
                self.check_services(data)
            except base.Timeout:
                pass

    @tornado.gen.coroutine
    def nginx_reload(self):
        while True:
            yield self.nginx_update_event.wait()
            self.nginx_update_event.clear()
            call(["nginx -s reload"], shell=True)
            print('nginx reload')

    def check_services(self, data):
        # check if service has any of our tags
        services_to_publish = dict((k, v) for k, v in data.items() if any(x in v for x in [u'http', u'http2']))
        for service_name in services_to_publish:
            print('New service: %s' % service_name)
            self.services[service_name] = Service(service_name)

        # cleanup stale services
        for service_name in self.services:
            if service_name not in services_to_publish.iterkeys():
                print('Removing stale service: %s' % service_name)
                del self.services[service_name]

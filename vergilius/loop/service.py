import os

from consul import tornado, base
from tornado import template

import config
import consul_handler
from loop.certificate import Certificate

nginx_config_path = os.environ.get('NGINX_CONFIG_PATH', '/etc/nginx/sites-enabled/')


class Service(object):
    tc = tornado.Consul(host=config.CONSUL_HOST)

    def __init__(self, name):
        """
        :type name: unicode - service name got from consul
        """
        self.name = name
        self.allow_crossdomain = False
        self.nodes = {}
        self.domains = {
            u'http': set(),
            u'http2': set()
        }

        self.active = True
        self.certificate = None
        self.watch()

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = yield self.tc.catalog.service(self.name, index, wait=None)
                self.parse_data(data)
            except base.Timeout:
                pass

    def parse_data(self, data):
        for protocol in self.domains.iterkeys():
            self.domains[protocol].clear()

        allow_crossdomain = False
        for node in data:
            self.nodes[node['Node']] = {
                'port': node[u'ServicePort'],
                'address': node[u'ServiceAddress'] or node[u'Address'],
                'tags': node[u'ServiceTags'],
            }

            if u'allow_crossdomain' in node[u'ServiceTags']:
                allow_crossdomain = True

            for protocol in [u'http', u'http2']:
                if protocol in node[u'ServiceTags']:
                    self.domains[protocol].update(
                            tag.replace(protocol + ':', '') for tag in node[u'ServiceTags'] if
                            tag.startswith(protocol + ':')
                    )

        self.allow_crossdomain = allow_crossdomain

        if len(self.domains[u'http2']):
            self.certificate = Certificate(self.name, self.domains[u'http2'])

        self.update_nginx_config()

    def update_nginx_config(self):
        loader = template.Loader('templates/')
        config = loader.load("service.html").generate(service=self)

        current_config = None

        try:
            config_file = open(self.get_nginx_config_path(), 'r')
            current_config = config_file.read()
            config_file.close()
        except IOError:
            pass

        if current_config != config:
            config_file = open(self.get_nginx_config_path(), 'w+')
            config_file.write(config)
            config_file.close()
            print('new config for %s' % self.name)
            consul_handler.ConsulHandler.nginx_update_event.set()

    def get_nginx_config_path(self):
        return nginx_config_path + self.name

    def __del__(self):
        """
        Destroy service, remove nginx config, stop watcher
        """
        self.active = False
        os.remove(self.get_nginx_config_path())

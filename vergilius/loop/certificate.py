import os

from consul import tornado, base, Consul

import config
from loop.acme_client import AcmeClient

nginx_config_path = os.environ.get('NGINX_CONFIG_PATH', '/etc/nginx/sites-enabled/')


class Certificate(object):
    tc = tornado.Consul(host=config.CONSUL_HOST)
    c = Consul(host=config.CONSUL_HOST)
    acme_client = AcmeClient()

    def __init__(self, service_name, domains):
        """
        :type name: unicode - service name got from consul
        """
        self.service_name = service_name
        self.domains = domains
        self.certificate_domains = []

        self.key = ''
        self.pem = ''

        self.active = True
        self.fetch()
        self.watch()

    def fetch(self):
        index, data = self.c.kv.get('vergilius/services/%s/cert/' % self.service_name, recurse=True)
        self.parse_data(data)

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = \
                    yield self.tc.kv.get('vergilius/services/%s/cert/' % self.service_name, index=index, recurse=True)
                self.parse_data(data)
            except base.Timeout:
                pass

    def parse_data(self, data):
        if data is None:
            self.request_certificate()
        else:
            for item in data:
                key = item['Key'].replace('vergilius/services/%s/cert/' % self.service_name, '')
                if hasattr(self, key):
                    setattr(self, key, item['Value'])

        self.write_certificate_files()

    def __del__(self):
        self.active = False
        # self.delete_certificate_files()

    def request_certificate(self):
        self.acme_client.request_certificate(self.domains)

        # self.c.kv.put('vergilius/services/%s/cert/key' % self.service_name, self.key)
        # self.c.kv.put('vergilius/services/%s/cert/pem' % self.service_name, self.pem)
        # self.c.kv.put('vergilius/services/%s/cert/certificate_domains' % self.service_name, self.domains)

    def write_certificate_files(self):
        key_file = open(self.get_key_path(), 'w+')
        key_file.write(self.key)
        key_file.close()

        pem_file = open(self.get_pem_path(), 'w+')
        pem_file.write(self.pem)
        pem_file.close()

    def delete_certificate_files(self):
        os.remove(self.get_key_path())
        os.remove(self.get_pem_path())

    def get_key_path(self):
        return nginx_config_path + 'certs/' + self.service_name + '.key'

    def get_pem_path(self):
        return nginx_config_path + 'certs/' + self.service_name + '.pem'

import os
import re
import unicodedata
import tempfile
import subprocess

from consul import tornado, base

from tornado.locks import Event

from vergilius import config, consul_tornado
from vergilius import logger, template_loader
from vergilius.models.certificate import Certificate


class Service(object):
    nginx_update_event = Event()

    def __init__(self, name):
        """
        :type name: unicode - service name got from consul
        """
        self.name = name
        self.id = self.slugify(name)
        logger.info('[service][%s]: new and loading' % self.name)
        self.allow_crossdomain = False
        self.nodes = {}
        self.domains = {
            u'http': set(),
            u'http2': set()
        }

        self.active = True
        self.certificate = None

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = yield consul_tornado.catalog.service(self.name, index, wait=None)
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

        self.flush_nginx_config()

    def get_nginx_config(self):
        """
        Generate nginx config from service attributes
        """
        if self.domains[u'http2']:
            self.check_certificate()
        return template_loader.load('service.html').generate(service=self, config=config)

    def flush_nginx_config(self):
        if not self.validate():
            logger.error('[service][%s]: failed to validate nginx config!' % self.id)
            return False

        nginx_config = self.get_nginx_config()
        deployed_nginx_config = None

        try:
            deployed_nginx_config = self.read_nginx_config_file()

        except IOError:
            pass

        if deployed_nginx_config != nginx_config:
            config_file = open(self.get_nginx_config_path(), 'w+')
            config_file.write(nginx_config)
            config_file.close()
            logger.info('[service][%s]: got new nginx config %s' % (self.name, self.get_nginx_config_path()))
            self.nginx_update_event.set()

    def get_nginx_config_path(self):
        return config.NGINX_CONFIG_PATH + self.id

    def read_nginx_config_file(self):
        with open(self.get_nginx_config_path(), 'r') as config_file:
            config_content = config_file.read()
            config_file.close()
            return config_content

    @tornado.gen.coroutine
    def nginx_reload(self):
        while True:
            yield self.nginx_update_event.wait()
            self.nginx_update_event.clear()
            logger.info('[nginx]: reload')
            subprocess.check_call([config.NGINX_BINARY, '-s', 'reload'])

    def validate(self):
        """
        Deploy temporary service & nginx config and validate it with nginx
        :return: bool
        """
        service_config_file = tempfile.NamedTemporaryFile(delete=False)
        service_config_file.write(self.get_nginx_config())
        service_config_file.close()

        nginx_config_file = tempfile.NamedTemporaryFile(delete=False)
        nginx_config_file.write(template_loader.load('service_validate.html')
                                .generate(service_config=service_config_file.name,
                                          pid_file='%s.pid' % service_config_file.name)
                                )
        nginx_config_file.close()

        try:
            return_code = subprocess.check_call([config.NGINX_BINARY, '-t', '-c', nginx_config_file.name])
        except subprocess.CalledProcessError:
            return_code = 1
        finally:
            os.unlink(service_config_file.name)
            os.unlink(nginx_config_file.name)

        return return_code == 0

    def delete(self):
        """
        Destroy service, remove nginx config, stop watcher
        """

        logger.info('[service][%s]: deleting' % self.name)
        self.active = False

        try:
            os.remove(self.get_nginx_config_path())
        except OSError:
            pass

    def __del__(self):
        if self.active:
            self.delete()

    @classmethod
    def slugify(cls, string):
        """
        Normalizes string, converts to lowercase, removes non-alpha characters,
        and converts spaces to hyphens.
        """
        string = unicodedata.normalize('NFKD', unicode(string)).encode('ascii', 'ignore')
        string = unicode(re.sub('[^\w\s-]', '', string).strip().lower())
        return re.sub('[-\s]+', '-', string)

    def check_certificate(self):
        if not self.certificate:
            self.certificate = Certificate(service=self, domains=self.domains[u'http2'])

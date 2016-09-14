import os
import re
import subprocess
import tempfile
import unicodedata

from consul import tornado, base
from vergilius import config, consul_tornado, consul, logger, template_loader
from vergilius.loop.nginx_reloader import NginxReloader
from vergilius.models.certificate import Certificate


class Service(object):
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

        if not os.path.exists(config.NGINX_CONFIG_PATH):
            os.mkdir(config.NGINX_CONFIG_PATH)

        self.fetch()
        self.watch()

    def fetch(self):
        index, data = consul.health.service(self.name, passing=True)
        self.parse_data(data)

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = yield consul_tornado.health.service(self.name, index, wait=None, passing=True)
                self.parse_data(data)
            except base.Timeout:
                pass

    def parse_data(self, data):
        """

        :type data: set[]
        """
        for protocol in self.domains.iterkeys():
            self.domains[protocol].clear()

        allow_crossdomain = False
        self.nodes = {}
        for node in data:
            if not node[u'Service'][u'Port']:
                logger.warn('[service][%s]: Node %s is ignored due no ServicePort' % (self.id, node[u'Node']))
                continue

            if node[u'Service']][u'Tags'] is None:
                logger.warn('[service][%s]: Node %s is ignored due no ServiceTags' % (self.id, node[u'Node']))
                continue

            self.nodes[node['Node']['Node']] = {
                'port': node[u'Service'][u'Port'],
                'address': node[u'Service'][u'Address'] or node[u'Node'][u'Address'],
                'tags': node[u'Service'][u'Tags'],
            }

            if u'allow_crossdomain' in node[u'Service'][u'Tags']:
                allow_crossdomain = True

            for protocol in [u'http', u'http2']:
                if protocol in node[u'Service'][u'Tags']:
                    self.domains[protocol].update(
                            tag.replace(protocol + ':', '') for tag in node[u'Service'][u'Tags'] if
                            tag.startswith(protocol + ':')
                    )

        self.allow_crossdomain = allow_crossdomain

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
            NginxReloader.queue_reload()

    def get_nginx_config_path(self):
        return os.path.join(config.NGINX_CONFIG_PATH, self.id + '.conf')

    def read_nginx_config_file(self):
        with open(self.get_nginx_config_path(), 'r') as config_file:
            config_content = config_file.read()
            config_file.close()
            return config_content

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
            os.unlink('%s.pid' % service_config_file.name)
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

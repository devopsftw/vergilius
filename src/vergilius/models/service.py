import os
import re
import subprocess
import tempfile
import unicodedata

import tornado.gen
from tornado.ioloop import IOLoop

import consul.base
from consul import ConsulException
from vergilius import config, consul_tornado, consul, logger, template_loader
from vergilius.loop.nginx_reloader import NginxReloader
from vergilius.models.certificate import Certificate


class Service(object):
    active = False

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
            'http': set(),
            'http2': set()
        }

        self.active = True
        self.certificate = None

        if not os.path.exists(config.NGINX_CONFIG_PATH):
            os.mkdir(config.NGINX_CONFIG_PATH)

        # spawn service watcher
        IOLoop.instance().spawn_callback(self.watch)

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = yield consul_tornado.health.service(self.name, index, wait=None, passing=True)
                yield self.parse_data(data)
                # okay, got data, now reload
                yield self.update_config()
            except ConsulException as e:
                logger.error('consul error: %s' % e)
                yield tornado.gen.sleep(5)
            except consul.base.Timeout:
                pass

    @tornado.gen.coroutine
    def parse_data(self, data):
        """

        :type data: set[]
        """
        for protocol in self.domains.keys():
            self.domains[protocol].clear()

        allow_crossdomain = False
        self.nodes = {}
        for node in data:
            if not node[u'Service'][u'Port']:
                logger.warn('[service][%s]: Node %s is ignored due no ServicePort' % (self.id, node[u'Node']))
                continue

            if node[u'Service'][u'Tags'] is None:
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

    @tornado.gen.coroutine
    def update_config(self):
        # if we have http2 domain, create stub nginx config for ACME
        if self.domains[u'http2']:

            # if we dont have certificate yet, create stub config and wait
            if not self.certificate:
                logger.debug('[service][%s] flush stub config' % self.id)
                self.flush_nginx_config(self.get_stub_config())
                self.certificate = Certificate(service=self, domains=self.domains[u'http2'])
                logger.debug('[service][%s] wait for cert' % self.id)
                yield self.certificate.ready_event.wait()
            logger.debug('[service][%s] load real https config' % self.id)
            self.flush_nginx_config(self.get_nginx_config())
        else:
            logger.debug('[service][%s] flush real config' % self.id)
            self.flush_nginx_config(self.get_nginx_config())

    def get_nginx_config(self):
        """
        Generate nginx config from service attributes
        """
        return template_loader.load('service.html').generate(service=self, config=config)

    def get_stub_config(self):
        return template_loader.load('service_stub.html').generate(service=self, config=config)

    def flush_nginx_config(self, nginx_config):
        if not self.validate(nginx_config):
            logger.error('[service][%s]: failed to validate nginx config!' % self.id)
            return False

        deployed_nginx_config = None

        try:
            deployed_nginx_config = self.read_nginx_config_file()
        except IOError:
            pass

        if deployed_nginx_config != nginx_config:
            config_file = open(self.get_nginx_config_path(), 'wb')
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

    def validate(self, config_str):
        """
        Deploy temporary service & nginx config and validate it with nginx
        :return: bool
        """
        service_config_file = tempfile.NamedTemporaryFile(delete=False)
        service_config_file.write(config_str)
        service_config_file.close()

        nginx_config_file = tempfile.NamedTemporaryFile(delete=False)
        nginx_config_file.write(template_loader.load('service_validate.html')
                                .generate(service_config=service_config_file.name,
                                          pid_file='%s.pid' % service_config_file.name)
                                )
        nginx_config_file.close()

        try:
            return_code = subprocess.check_call([config.NGINX_BINARY, '-t', '-c', nginx_config_file.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        string = unicodedata.normalize('NFKD', string)
        string = string.encode('ascii', 'ignore').decode()
        string = str(re.sub('[^\w\s-]', '', str(string)).strip().lower())
        return re.sub('[-\s]+', '-', string)

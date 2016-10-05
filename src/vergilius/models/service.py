import os
import re
import subprocess
import tempfile
import unicodedata

import itertools
from consul import tornado, base, ConsulException
from shutil import rmtree

from vergilius import config, consul_tornado, consul, logger, template_loader
from vergilius.components import port_allocator
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
        self.port = None
        self.binds = {
            u'http': set(),
            u'http2': set(),
            u'tcp': set(),
            u'udp': set()
        }

        self.active = True
        self.certificate = None

        if not os.path.exists(config.NGINX_CONFIG_PATH):
            os.mkdir(config.NGINX_CONFIG_PATH)

        self.fetch()
        self.watch()

    def fetch(self):
        index, data = consul.health.service(self.id, passing=True)
        self.parse_data(data)

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = yield consul_tornado.health.service(self.id, index, wait=None, passing=True)
                self.parse_data(data)
            except ConsulException as e:
                logger.error('consul exception: %s' % e)
            except base.Timeout:
                pass

    def parse_data(self, data):
        """

        :type data: set[]
        """
        for protocol in self.binds.iterkeys():
            self.binds[protocol].clear()

        allow_crossdomain = False
        self.nodes = {}
        for node in data:
            if not node[u'Service'][u'Port']:
                logger.warn('[service][%s]: Node %s is ignored due no Service Port' % (self.id, node[u'Node'][u'Node']))
                continue

            if node[u'Service'][u'Tags'] is None:
                logger.warn('[service][%s]: Node %s is ignored due no Service Tags' % (self.id, node[u'Node'][u'Node']))
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
                    self.binds[protocol].update(
                            tag.replace(protocol + ':', '') for tag in node[u'Service'][u'Tags'] if
                            tag.startswith(protocol + ':')
                    )

            for protocol in ['tcp', 'udp']:
                self.binds[protocol].update({node[u'Service'][u'Port']})

        self.allow_crossdomain = allow_crossdomain

        self.flush_nginx_config()

    def get_nginx_config(self, config_type):
        """
        Generate nginx config from service attributes
        :param config_type: string
        """
        if config_type == 'http2' and len(self.binds['http2']):
            self.check_certificate()

        if config_type in ['tcp', 'udp']:
            self.check_port()

        return template_loader.load('service_%s.html' % config_type).generate(service=self, config=config)

    def flush_nginx_config(self):
        if not self.validate():
            logger.error('[service][%s]: failed to validate nginx config!' % self.id)
            return False

        has_changes = False

        for config_type in self.get_config_types():
            nginx_config = self.get_nginx_config(config_type)
            deployed_nginx_config = None

            try:
                deployed_nginx_config = self.read_nginx_config_file(config_type)
            except IOError:
                pass

            if deployed_nginx_config != nginx_config:
                config_file = open(self.get_nginx_config_path(config_type), 'w+')
                config_file.write(nginx_config)
                config_file.close()
                has_changes = True

        if has_changes:
            NginxReloader.queue_reload()
            logger.info('[service][%s]: got new nginx config' % self.name)

    def get_nginx_config_path(self, config_type):
        return os.path.join(config.NGINX_CONFIG_PATH, '%s.%s.conf' % (self.id, config_type))

    def read_nginx_config_file(self, config_type):
        with open(self.get_nginx_config_path(config_type), 'r') as config_file:
            config_content = config_file.read()
            config_file.close()
            return config_content

    def get_config_types(self):
        return itertools.chain(self.binds.keys(), ['upstream'])

    def validate(self):
        """
        Deploy temporary service & nginx config and validate it with nginx
        :return: bool
        """

        temp_dir = tempfile.mkdtemp()

        files = {}
        for config_type in self.get_config_types():
            path = os.path.join(temp_dir, config_type)
            config_file = open(path, 'w+')
            config_file.write(self.get_nginx_config(config_type))
            config_file.close()
            files['service_%s' % config_type] = path

        files['pid_file'] = os.path.join(temp_dir, 'pid')

        nginx_config_file = open(os.path.join(temp_dir, 'service'), 'w+')
        nginx_config_file.write(template_loader.load('service_validate.html').generate(**files))
        nginx_config_file.close()

        try:
            return_code = subprocess.check_call([config.NGINX_BINARY, '-t', '-c', nginx_config_file.name])
        except subprocess.CalledProcessError:
            return_code = 1
        finally:
            rmtree(temp_dir, ignore_errors=True)

        return return_code == 0

    def delete(self):
        """
        Destroy service, remove nginx config, stop watcher
        """

        logger.info('[service][%s]: deleting' % self.name)
        self.active = False

        if self.port:
            self.release_port()

        for config_type in self.get_config_types():
            try:
                os.remove(self.get_nginx_config_path(config_type))
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
            self.certificate = Certificate(service=self, domains=self.binds['http2'])

    def check_port(self):
        if not self.port:
            self.port = port_allocator.allocate()
            consul.kv.put('vergilius/ports/%s' % self.name, str(self.port))

    def release_port(self):
        if self.port:
            port_allocator.release(self.port)
            consul.kv.delete('vergilius/ports/%s' % self.name)

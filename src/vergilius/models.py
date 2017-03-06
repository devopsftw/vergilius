import os
import logging
import re
import subprocess
import tempfile
import unicodedata
from datetime import datetime

import tornado.gen
import tornado.template
from tornado.ioloop import IOLoop
from tornado.locks import Event

from consul import Consul, ConsulException
from consul.base import Timeout as ConsulTimeout
from consul.tornado import Consul as TornadoConsul

from vergilius import config

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)

template_loader = tornado.template.Loader(config.TEMPLATE_PATH)
tc = TornadoConsul(host=config.CONSUL_HOST)
cc = Consul(host=config.CONSUL_HOST)


class Service(object):
    def __init__(self, name, app):
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
        self.app = app

        if not os.path.exists(config.NGINX_CONFIG_PATH):
            os.mkdir(config.NGINX_CONFIG_PATH)

        # spawn service watcher
        IOLoop.instance().spawn_callback(self.watch)

    @tornado.gen.coroutine
    def watch(self):
        index = old_nodes = None
        while True and self.active:
            try:
                index, data = yield tc.health.service(self.name, index, wait=None, passing=True)
                nodes = sorted([{k: svc[k] for k in svc if k != 'Checks'} for svc in data],
                               key=lambda x: x['Node']['Node'])
                if old_nodes != nodes:
                    # okay, got data, now parse and reload
                    yield self.parse_data(data)
                    yield self.update_config()
                    old_nodes = nodes
            except ConsulTimeout:
                pass
            except ConsulException as e:
                logger.error('consul error: %s' % e)
                yield tornado.gen.sleep(5)

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
                logger.warning('[service][%s]: Node %s is ignored due no ServicePort' % (self.id, node[u'Node']))
                continue

            if node[u'Service'][u'Tags'] is None:
                logger.warning('[service][%s]: Node %s is ignored due no ServiceTags' % (self.id, node[u'Node']))
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
        :rtype: bytes
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
            self.app.nginx_reloader.queue_reload()

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

        result = False
        try:
            subprocess.run(
                [config.NGINX_BINARY, '-t', '-c', nginx_config_file.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                check=True
            )
            result = True
        except subprocess.CalledProcessError as e:
            logger.error('[service][%s] nginx config check failed. stderr: ' % self.id, e.stderr)
        finally:
            os.unlink(service_config_file.name)
            os.unlink('%s.pid' % service_config_file.name)
            os.unlink(nginx_config_file.name)
        return result

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


class Certificate(object):
    def __init__(self, service, domains):
        """
        :type domains: set
        :type service: Service - service name got from consul
        """
        self.ready_event = Event()
        self.is_valid = False
        self.expires = 0
        self.service = service
        self.domains = sorted(domains)
        self.key_domains = ''
        self.id = '|'.join(self.domains)

        self.private_key = None
        self.public_key = None

        self.active = True
        self.lock_session_id = None

        self.certificate_provider = self.service.app.certificate_provider

        if not os.path.exists(os.path.join(config.NGINX_CONFIG_PATH, 'certs')):
            os.mkdir(os.path.join(config.NGINX_CONFIG_PATH, 'certs'))

        IOLoop.instance().add_callback(self.unlock)
        IOLoop.instance().spawn_callback(self.watch)

    @tornado.gen.coroutine
    def fetch(self, index):
        index, data = yield tc.kv.get('vergilius/certificates/%s/' % self.service.id, index=index, recurse=True)
        return index, data

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = yield self.fetch(index)
                yield self.load_keys_from_consul(data)
            except ConsulTimeout:
                pass
            except ConsulException as e:
                logger.error('consul error: %s' % e)
                yield tornado.gen.sleep(5)

    @tornado.gen.coroutine
    def load_keys_from_consul(self, data=None):
        if data:
            for item in data:
                key = item['Key'].replace('vergilius/certificates/%s/' % self.service.id, '')
                if hasattr(self, key):
                    setattr(self, key, item['Value'])

            if self.validate():
                self.is_valid = True
                logger.debug('[certificate][%s]: using existing keys' % self.service.id)
            else:
                logger.warning('[certificate][%s]: cant validate existing keys' % self.service.id)
                self.discard_certificate()
                if not (yield self.request_certificate()):
                    self.ready_event.set()
                    return False
        else:
            if not (yield self.request_certificate()):
                self.ready_event.set()
                return False

        self.write_certificate_files()
        self.ready_event.set()
        return True

    def write_certificate_files(self):
        key_file = open(self.get_key_path(), 'wb')
        key_file.write(self.private_key)
        key_file.close()

        pem_file = open(self.get_cert_path(), 'wb')
        pem_file.write(self.public_key)
        pem_file.close()

    def delete_certificate_files(self):
        if os.path.exists(self.get_key_path()):
            os.remove(self.get_key_path())
        if os.path.exists(self.get_cert_path()):
            os.remove(self.get_cert_path())

    def get_key_path(self):
        return os.path.join(config.NGINX_CONFIG_PATH, 'certs', self.service.id + '.key')

    def get_cert_path(self):
        return os.path.join(config.NGINX_CONFIG_PATH, 'certs', self.service.id + '.pem')

    @tornado.gen.coroutine
    def acquire_lock(self):
        """
        Create a lock in consul to prevent certificate request race condition
        """
        self.lock_session_id = yield self.service.app.session.get_sid()
        result = yield tc.kv.put('vergilius/locks/cert/%s' % self.service.id, '', acquire=self.lock_session_id)
        return result

    @tornado.gen.coroutine
    def unlock(self):
        if not self.lock_session_id:
            return

        yield tc.kv.put('vergilius/locks/cert/%s' % self.service.id, '', release=self.lock_session_id)
        self.lock_session_id = None

    @tornado.gen.coroutine
    def request_certificate(self):
        logger.debug('[certificate][%s] Requesting new keys for %s ' % (self.service.name, self.domains))

        if not (yield self.acquire_lock()):
            logger.debug('[certificate][%s] failed to acquire lock for keys generation' % self.service.name)
            return False

        try:
            data = yield self.certificate_provider.get_certificate(self.domains)

            if data is None:
                logger.error('certificate get failed for service %s' % self.service.name)
                return False

            self.private_key = data['private_key']
            cc.kv.put('vergilius/certificates/%s/private_key' % self.service.id, self.private_key)

            self.public_key = data['public_key']
            cc.kv.put('vergilius/certificates/%s/public_key' % self.service.id, self.public_key)

            self.expires = data['expires']
            self.key_domains = self.serialize_domains()
            logger.debug('write domain %s' % self.key_domains)
            cc.kv.put('vergilius/certificates/%s/expires' % self.service.id, str(self.expires))
            cc.kv.put('vergilius/certificates/%s/key_domains' % self.service.id, self.serialize_domains())
            logger.info('[certificate][%s]: got new keys for %s ' % (self.service.name, self.domains))
            self.write_certificate_files()
            self.is_valid = True
        except Exception as e:
            logger.error('[certificate][%s]: certificate request error, discarding: %s' % (self.service.id, e))
            self.is_valid = False
        finally:
            yield self.unlock()

    def serialize_domains(self):
        return '|'.join(sorted(self.domains)).encode()

    def discard_certificate(self):
        pass

    def validate(self):
        if not self.private_key or not self.public_key:
            logger.warning('[certificate][%s]: validation error: empty key' % self.service.id)
            return False

        try:
            serialization.load_pem_private_key(self.private_key, password=None, backend=default_backend())
        except:
            logger.warning('[certificate][%s]: private key load error: expired' % self.service.id, exc_info=True)
            return False

        cert = x509.load_pem_x509_certificate(self.public_key, default_backend())  # type: x509.Certificate
        if datetime.now() > cert.not_valid_after:
            logger.warning('[certificate][%s]: validation error: expired' % self.service.id)
            return False

        # TODO: get domain names from cert
        if self.key_domains != self.serialize_domains():
            logger.warning('[certificate][%s]: validation error: domains mismatch: %s != %s' %
                           (self.service.id, self.key_domains, self.serialize_domains()))
            return False

        return True

    def __del__(self):
        self.active = False
        self.delete_certificate_files()

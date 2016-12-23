import os
import time
from datetime import datetime

from tornado.ioloop import IOLoop
from tornado.locks import Event
import tornado.gen

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from consul import Consul, ConsulException
from consul.base import Timeout as ConsulTimeout
from consul.tornado import Consul as TornadoConsul
from vergilius import Vergilius, logger, config


class Certificate(object):
    tc = TornadoConsul(host=config.CONSUL_HOST)
    cc = Consul(host=config.CONSUL_HOST)
    ready_event = Event()

    def __init__(self, service, domains):
        """
        :type domains: set
        :type service: Service - service name got from consul
        """
        self.expires = 0
        self.service = service
        self.domains = sorted(domains)
        self.key_domains = ''
        self.id = '|'.join(self.domains)

        self.private_key = None
        self.public_key = None

        self.active = True
        self.lock_session_id = None

        if not os.path.exists(os.path.join(config.NGINX_CONFIG_PATH, 'certs')):
            os.mkdir(os.path.join(config.NGINX_CONFIG_PATH, 'certs'))

        IOLoop.instance().add_callback(self.unlock)
        IOLoop.instance().spawn_callback(self.watch)

    @tornado.gen.coroutine
    def fetch(self, index):
        index, data = yield self.tc.kv.get('vergilius/certificates/%s/' % self.service.id, index=index, recurse=True)
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

            if not self.validate():
                logger.warn('[certificate][%s]: cant validate existing keys' % self.service.id)
                self.discard_certificate()
                if not (yield self.request_certificate()):
                    return False
            else:
                logger.debug('[certificate][%s]: using existing keys' % self.service.id)
        else:
            if not (yield self.request_certificate()):
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

    def acquire_lock(self):
        """
        Create a lock in consul to prevent certificate request race condition
        """
        self.lock_session_id = self.cc.session.create(behavior='delete', ttl=10)
        return self.cc.kv.put('vergilius/certificates/%s/lock' % self.service.id, '', acquire=self.lock_session_id)

    def unlock(self):
        if not self.lock_session_id:
            return

        self.cc.kv.put('vergilius/certificates/%s/lock' % self.service.id, '', release=self.lock_session_id)
        self.cc.session.destroy(self.lock_session_id)
        self.lock_session_id = None

    @tornado.gen.coroutine
    def request_certificate(self):
        logger.debug('[certificate][%s] Requesting new keys for %s ' % (self.service.name, self.domains))

        if not self.acquire_lock():
            logger.debug('[certificate][%s] failed to acquire lock for keys generation' % self.service.name)
            return False

        try:
            data = yield Vergilius.instance().certificate_provider.get_certificate(self.service.id, self.domains)

            self.private_key = data['private_key']
            self.cc.kv.put('vergilius/certificates/%s/private_key' % self.service.id, self.private_key)

            self.public_key = data['public_key']
            self.cc.kv.put('vergilius/certificates/%s/public_key' % self.service.id, self.public_key)

            self.expires = data['expires']
            self.key_domains = self.serialize_domains()
            logger.debug('write domain %s' % self.key_domains)
            self.cc.kv.put('vergilius/certificates/%s/expires' % self.service.id, str(self.expires))
            self.cc.kv.put('vergilius/certificates/%s/key_domains' % self.service.id, self.serialize_domains())
            logger.info('[certificate][%s]: got new keys for %s ' % (self.service.name, self.domains))
            self.write_certificate_files()
        except Exception as e:
            logger.error(e)
            raise e
        finally:
            self.unlock()

    def serialize_domains(self):
        return '|'.join(sorted(self.domains)).encode()

    def discard_certificate(self):
        pass

    def validate(self):
        if not len(self.private_key) or not len(self.public_key):
            logger.warn('[certificate][%s]: validation error: empty key' % self.service.id)
            return False

        try:
            serialization.load_pem_private_key(self.private_key, password=None, backend=default_backend())
        except:
            logger.warn('[certificate][%s]: private key load error: expired' % self.service.id)
            return False

        cert = x509.load_pem_x509_certificate(self.public_key, default_backend()) # type: x509.Certificate
        if datetime.now() > cert.not_valid_after:
            logger.warn('[certificate][%s]: validation error: expired' % self.service.id)
            return False

        # TODO: get domain names from cert
        if self.key_domains != self.serialize_domains():
            logger.warn('[certificate][%s]: validation error: domains mismatch: %s != %s' %
                        (self.service.id, self.key_domains, self.serialize_domains()))
            return False

        return True

    def __del__(self):
        self.active = False
        self.delete_certificate_files()

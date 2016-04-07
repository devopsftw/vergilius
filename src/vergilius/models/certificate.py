import os
import time
from tornado import ioloop

from consul import tornado, base
from vergilius import consul, logger, certificate_provider, config

if not os.path.exists(os.path.join(config.NGINX_CONFIG_PATH, 'certs')):
    os.mkdir(os.path.join(config.NGINX_CONFIG_PATH, 'certs'))

class Certificate(object):
    tc = tornado.Consul(host=config.CONSUL_HOST)

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

        ioloop.IOLoop.instance().add_callback(self.unlock)
        self.fetch()
        self.watch()

    def fetch(self):
        index, data = consul.kv.get('vergilius/certificates/%s/' % self.service.id, recurse=True)
        self.load_keys_from_consul(data)

    @tornado.gen.coroutine
    def watch(self):
        index = None
        while True and self.active:
            try:
                index, data = \
                    yield self.tc.kv.get('vergilius/certificates/%s/' % self.service.id, index=index, recurse=True)
                self.load_keys_from_consul(data)
            except base.Timeout:
                pass

    def load_keys_from_consul(self, data=None):
        if data:
            for item in data:
                key = item['Key'].replace('vergilius/certificates/%s/' % self.service.id, '')
                if hasattr(self, key):
                    setattr(self, key, item['Value'])

            if not self.validate():
                logger.warn('[certificate][%s]: cant validate existing keys' % self.service.id)
                self.discard_certificate()
                if not self.request_certificate():
                    return False
            else:
                logger.debug('[certificate][%s]: using existing keys' % self.service.id)
        else:
            if not self.request_certificate():
                return False

        self.write_certificate_files()
        return True

    def write_certificate_files(self):
        key_file = open(self.get_key_path(), 'w+')
        key_file.write(self.private_key)
        key_file.close()

        pem_file = open(self.get_cert_path(), 'w+')
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

    def lock(self):
        """
        Create a lock in consul to prevent certificate request race condition
        """
        self.lock_session_id = consul.session.create(behavior='delete')
        return consul.kv.put('vergilius/certificates/%s/lock' % self.service.id, '', acquire=self.lock_session_id)

    def unlock(self):
        if not self.lock_session_id:
            return

        # consul.kv.put('vergilius/certificates/%s/lock' % self.service.id, '', release=self.lock_session_id)
        consul.session.destroy(self.lock_session_id)
        self.lock_session_id = None

    def request_certificate(self):
        logger.debug('[certificate][%s] Requesting new keys for %s ' % (self.service.name, self.domains))

        if not self.lock():
            logger.debug('[certificate][%s] failed to acquire lock for keys generation' % self.service.name)
            return False

        data = certificate_provider.get_certificate(self.service.id, self.domains)

        with open(data['private_key'], 'r') as f:
            self.private_key = f.read()
            f.close()
            consul.kv.put('vergilius/certificates/%s/private_key' % self.service.id, self.private_key)

        with open(data['public_key'], 'r') as f:
            self.public_key = f.read()
            f.close()
            consul.kv.put('vergilius/certificates/%s/public_key' % self.service.id, self.public_key)

        self.expires = data['expires']
        self.key_domains = self.serialize_domains()
        consul.kv.put('vergilius/certificates/%s/expires' % self.service.id, str(self.expires))
        consul.kv.put('vergilius/certificates/%s/key_domains' % self.service.id, self.serialize_domains())
        self.unlock()
        logger.info('[certificate][%s]: got new keys for %s ' % (self.service.name, self.domains))

    def serialize_domains(self):
        return '|'.join(sorted(self.domains))

    def discard_certificate(self):
        pass

    def validate(self):
        if int(self.expires) < int(time.time()):
            logger.warn('[certificate][%s]: validation error: expired' % self.service.id)
            return False

        if self.key_domains != self.serialize_domains():
            logger.warn('[certificate][%s]: validation error: domains mismatch: %s != %s' %
                        (self.service.id, self.key_domains, self.serialize_domains()))
            return False

        if not len(self.private_key) or not len(self.public_key):
            logger.warn('[certificate][%s]: validation error: empty key' % self.service.id)
            return False

        return True

    def __del__(self):
        self.active = False
        self.delete_certificate_files()

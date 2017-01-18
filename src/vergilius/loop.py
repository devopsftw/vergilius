import logging
import subprocess

from consul.tornado import Consul as TornadoConsul
from consul import ConsulException
from consul.base import Timeout as ConsulTimeout

from vergilius import config
from vergilius.models import Service

import tornado.gen
from tornado.locks import Event

logger = logging.getLogger(__name__)
tc = TornadoConsul(host=config.CONSUL_HOST)


class NginxReloader(object):
    nginx_update_event = Event()

    def __init__(self):
        pass

    @classmethod
    @tornado.gen.coroutine
    def reload(cls):
        while True:
            yield cls.nginx_update_event.wait()
            cls.nginx_update_event.clear()
            logger.info('nginx reload')
            try:
                subprocess.check_call([config.NGINX_BINARY, '-s', 'reload'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logger.error('nginx reload fail. stderr: %s' % e.stderr)

    @classmethod
    def queue_reload(cls):
        cls.nginx_update_event.set()


class ServiceWatcher(object):
    def __init__(self, app):
        self.services = {}

        self.data = {}
        self.modified = False
        self.app = app

    @tornado.gen.coroutine
    def watch_services(self):
        index = None
        while True:
            try:
                index, data = yield tc.catalog.services(index, wait=None)
                self.check_services(data)
            except ConsulTimeout:
                pass
            except ConsulException as e:
                logger.error('consul error: %s' % e)
                yield tornado.gen.sleep(5)

    def check_services(self, data):
        # check if service has any of our tags
        services_to_publish = dict((k, v) for k, v in data.items() if any(x in v for x in [u'http', u'http2']))
        for service_name in services_to_publish:
            if service_name not in self.services:
                logger.info('[service watcher]: new service: %s' % service_name)
                self.services[service_name] = Service(service_name, self.app)

        # cleanup stale services
        for service_name in self.services.keys():
            if service_name not in services_to_publish.keys():
                logger.info('[service watcher]: removing stale service: %s' % service_name)
                del self.services[service_name]

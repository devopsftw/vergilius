from consul import tornado, base

from models.service import Service
from vergilius import logger, consul_tornado

class ServiceWatcher(object):
    def __init__(self):
        self.services = {}

        self.data = {}
        self.modified = False
        self.watch_services()

    @tornado.gen.coroutine
    def watch_services(self):
        index = None
        while True:
            try:
                index, data = yield consul_tornado.catalog.services(index, wait=None)
                self.check_services(data)
            except base.Timeout:
                pass

    def check_services(self, data):
        # check if service has any of our tags
        services_to_publish = dict((k, v) for k, v in data.items() if any(x in v for x in [u'http', u'http2']))
        for service_name in services_to_publish:
            logger.info('[service watcher]: new service: %s' % service_name)
            self.services[service_name] = Service(service_name)

        # cleanup stale services
        for service_name in self.services.keys():
            if service_name not in services_to_publish.iterkeys():
                logger.info('[service watcher]: removing stale service: %s' % service_name)
                del self.services[service_name]

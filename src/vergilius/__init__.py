import logging
import os

from consul import Consul
from consul import tornado as consul_from_tornado
from tornado import template

import vergilius.config
from vergilius.components.dummy_certificate_provider import DummyCertificateProvider
from vergilius.components.acme_certificate_provider import AcmeCertificateProvider
from vergilius.models.identity import Identity
from vergilius.session import ConsulSession

logger = logging.getLogger(__name__)
template_loader = template.Loader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))

consul = Consul(host=config.CONSUL_HOST)
consul_tornado = consul_from_tornado.Consul(host=config.CONSUL_HOST)


class Vergilius(object):
    identity = None

    session = None

    certificate_provider = None

    __instance = None

    def __new__(cls):
        if Vergilius.__instance is None:
            Vergilius.__instance = object.__new__(cls)
            Vergilius.__instance.init()
        return Vergilius.__instance

    @classmethod
    def instance(cls):
        return cls.__instance

    def init(self):
        self.session = ConsulSession()
        self.identity = Identity()
        self.certificate_provider = AcmeCertificateProvider(session=self.session)

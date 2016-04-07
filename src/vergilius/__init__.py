import logging
import os

from consul import Consul
from consul import tornado as consul_from_tornado
from tornado import template

import config
from components.dummy_certificate_provider import DummyCertificateProvider
from vergilius.models.identity import Identity

logger = logging.getLogger(__name__)
template_loader = template.Loader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
certificate_provider = DummyCertificateProvider()

consul = Consul(host=config.CONSUL_HOST)
consul_tornado = consul_from_tornado.Consul(host=config.CONSUL_HOST)
identity = Identity()

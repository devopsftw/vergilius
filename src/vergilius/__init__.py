import logging
import os

from consul import Consul
from consul.tornado import Consul as ConsulTornado
from tornado import template

import vergilius.config
import vergilius.base
import vergilius.cert

logger = logging.getLogger(__name__)
template_loader = template.Loader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))

consul = Consul(host=config.CONSUL_HOST)
consul_tornado = ConsulTornado(host=config.CONSUL_HOST)
session = vergilius.base.ConsulSession()
identity = vergilius.base.Identity()
certificate_provider = vergilius.cert.AcmeCertificateProvider()

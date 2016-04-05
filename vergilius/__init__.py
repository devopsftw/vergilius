#!/usr/bin/python
import os
import sys
import tornado
import logging

from consul import Consul
from consul import tornado as consul_from_tornado
from tornado import template

import vergilius
import vergilius.config
from components.dummy_certificate_provider import DummyCertificateProvider
from web.main_handler import make_app

logger = logging.getLogger(__name__)
template_loader = template.Loader(os.path.join(os.path.dirname(vergilius.__file__), 'templates'))
certificate_provider = DummyCertificateProvider()

consul = Consul(host=config.CONSUL_HOST)
consul_tornado = consul_from_tornado.Consul(host=config.CONSUL_HOST)

out_hdlr = logging.StreamHandler(sys.stdout)
out_hdlr.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_hdlr.setLevel(logging.DEBUG)

logger.addHandler(out_hdlr)
logger.setLevel(logging.DEBUG)

if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    # consul_handler = ConsulHandler()
    tornado.ioloop.IOLoop.current().start()

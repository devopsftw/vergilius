import logging
import os
import unittest

import sys
import shutil
import tornado.ioloop
import tornado.testing

os.environ.setdefault('SECRET', 'test')
import vergilius.base
import vergilius.cert
import vergilius.loop
import vergilius.config

from consul import Consul

out_hdlr = logging.StreamHandler(sys.stdout)
out_hdlr.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_hdlr.setLevel(logging.DEBUG)

logger = logging.getLogger('tests')
logger.addHandler(out_hdlr)
logger.setLevel(logging.DEBUG)

cc = Consul()


def start_tornado():
    tornado.ioloop.IOLoop.instance().start()


class MockApp(object):
    def __init__(self):
        self.session = vergilius.base.ConsulSession()
        self.certificate_provider = vergilius.cert.DummyCertificateProvider()
        self.nginx_reloader = vergilius.loop.NginxReloader()


class BaseAsyncTest(tornado.testing.AsyncTestCase):
    def setUp(self):
        super(BaseAsyncTest, self).setUp()
        self.app = MockApp()
        cc.kv.delete('vergilius', True)

        try:
            os.mkdir(vergilius.config.DATA_PATH)
            os.mkdir(vergilius.config.NGINX_CONFIG_PATH)
        except OSError as e:
            print(e)

    def tearDown(self):
        super(BaseAsyncTest, self).tearDown()
        shutil.rmtree(vergilius.config.NGINX_CONFIG_PATH)
        shutil.rmtree(vergilius.config.DATA_PATH)

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.instance()
import logging
import os
import threading
import unittest

import sys
import shutil
import tornado

os.environ.setdefault('SECRET', 'test')
import vergilius.base
import vergilius.cert
import vergilius.loop

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


class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(BaseTest, cls).setUpClass()
        cls.app = MockApp()
        cls.watcher = vergilius.loop.ServiceWatcher(cls.app)
        cls.watcher.watch_services()

        threading.Thread(target=start_tornado).start()

    @classmethod
    def tearDownClass(cls):
        super(BaseTest, cls).tearDownClass()
        tornado.ioloop.IOLoop.instance().stop()

    def setUp(self):
        super(BaseTest, self).setUp()
        cc.kv.delete('vergilius', True)

        try:
            os.mkdir(vergilius.config.DATA_PATH)
            os.mkdir(vergilius.config.NGINX_CONFIG_PATH)
        except OSError as e:
            print(e)

    def tearDown(self):
        super(BaseTest, self).tearDown()
        cc.kv.delete('vergilius', True)

        shutil.rmtree(vergilius.config.NGINX_CONFIG_PATH)
        shutil.rmtree(vergilius.config.DATA_PATH)

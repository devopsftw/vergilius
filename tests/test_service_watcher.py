import threading
import time
import unittest

import tornado
from vergilius import consul
from vergilius.loop.service_watcher import ServiceWatcher


def start_tornado():
    tornado.ioloop.IOLoop.instance().start()


class Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.watcher = ServiceWatcher()
        threading.Thread(target=start_tornado).start()

    @classmethod
    def tearDownClass(cls):
        tornado.ioloop.IOLoop.instance().stop()

    def setUp(self):
        super(Test, self).setUp()
        consul.kv.delete('vergilius', True)

    def tearDown(self):
        consul.agent.service.deregister('test')

    def test_poll(self):
        consul.agent.service.register('test', 'test', tags=['http'], port=80)
        time.sleep(1)
        self.assertTrue(self.watcher.services['test'], 'service registered')
        consul.agent.service.deregister('test')
        time.sleep(1)
        self.assertFalse('test' in self.watcher.services.keys(), 'service unregistered')

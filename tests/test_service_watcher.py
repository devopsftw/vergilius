import threading
import unittest
import time
import tornado

from loop.service_watcher import ServiceWatcher
from vergilius import consul


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
        consul.agent.service.register('test', 'test', tags=['http'])
        time.sleep(0.2)
        self.assertTrue(self.watcher.services['test'], 'service registered')
        consul.agent.service.deregister('test')
        time.sleep(0.2)
        self.assertFalse('test' in self.watcher.services.keys(), 'service unregistered')

import time

from base_test import BaseTest
from vergilius import consul


class Test(BaseTest):
    def test_poll(self):
        consul.agent.service.register('test', 'test', tags=['http'], port=80)
        time.sleep(2)
        self.assertTrue('test' in self.watcher.services, 'service registered')
        consul.agent.service.deregister('test')
        time.sleep(1)
        self.assertFalse('test' in self.watcher.services.keys(), 'service unregistered')

    def test_empty_service(self):
        consul.agent.service.register('test', 'test')

        time.sleep(2)
        self.assertFalse('test' in self.watcher.services, 'service not registered')

    def tearDown(self):
        consul.agent.service.deregister('test')

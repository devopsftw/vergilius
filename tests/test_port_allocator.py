import time

from base_test import BaseTest
from vergilius import consul
from vergilius.components import port_allocator


class Test(BaseTest):
    def test_poll(self):
        consul.agent.service.register('test', 'test', tags=['tcp'], port=80)
        consul.agent.service.register('test2', 'test2', tags=['tcp'], port=80)
        time.sleep(2)
        self.assertTrue('test' in self.watcher.services, 'service registered')
        port_allocator.collect_garbage({'test': self.watcher.services.get('test')})
        test_service = self.watcher.services.get('test')
        self.assertEqual(test_service.port, port_allocator.allocated[test_service.id])

        consul.agent.service.deregister('test')
        time.sleep(2)
        self.assertFalse('test' in self.watcher.services.keys(), 'service unregistered')
        self.assertFalse(port_allocator.allocated.get(test_service.id))

        self.assertIsNotNone(port_allocator.allocated.get('test2'))

    def test_port_reuse(self):
        consul.kv.put('vergilius/ports/test', '7500')
        port_allocator.get_ports_from_consul()
        consul.agent.service.register('test', 'test', tags=['tcp'], port=80)

        time.sleep(2)
        self.assertTrue('test' in self.watcher.services, 'service registered')
        test_service = self.watcher.services.get('test')
        self.assertEqual(test_service.port, 7500)

    def tearDown(self):
        consul.agent.service.deregister('test')
        consul.agent.service.deregister('test2')
        consul.kv.delete('vergilius/ports', recurse=True)
        super(BaseTest, self).tearDown()

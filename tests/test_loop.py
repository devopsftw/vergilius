import tornado.testing
from base_test import BaseAsyncTest, cc
import vergilius.loop


class ServiceWatcherTest(BaseAsyncTest):
    def setUp(self):
        super().setUp()
        self.watcher = vergilius.loop.ServiceWatcher(self.app)

    def tearDown(self):
        super(ServiceWatcherTest, self).tearDown()
        cc.agent.service.deregister('test')

    @tornado.testing.gen_test
    def test_poll(self):
        cc.agent.service.register('test', 'test', tags=['http'], port=80)
        yield self.watcher.fetch_services()
        self.assertTrue('test' in self.watcher.services, 'service registered')

        cc.agent.service.deregister('test')
        yield self.watcher.fetch_services()
        self.assertFalse('test' in self.watcher.services.keys(), 'service unregistered')

    @tornado.testing.gen_test
    def test_empty_service(self):
        cc.agent.service.register('test', 'test')
        yield self.watcher.fetch_services()
        self.assertFalse('test' in self.watcher.services, 'service not registered')

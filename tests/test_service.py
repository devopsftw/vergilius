
from base_test import BaseTest
from vergilius.models import Service
from consul import Consul

cc = Consul()


class Test(BaseTest):
    def setUp(self):
        super(Test, self).setUp()
        cc.kv.delete('vergilius', True)

    def test_watcher(self):
        pass

    def test_base(self):
        service = Service(name='test service')
        service.flush_nginx_config()

        config_file = service.get_nginx_config_path()
        self.assertNotEqual(service.read_nginx_config_file().find('server 127.0.0.1:6666'), -1,
                            'config written and has backup 503')
        self.assertTrue(service.validate(), 'nginx config is valid')
        service.delete()

        with self.assertRaises(IOError):
            open(config_file, 'r')

    def test_http(self):
        service = Service(name='test service')

        service.domains[u'http'] = ('example.com',)

        self.assertNotEqual(service.get_nginx_config().find('server_name example.com *.example.com;'), -1,
                            'server_name and wildcard present')
        self.assertTrue(service.validate(), 'nginx config is valid')

    def test_http2(self):
        service = Service(name='test service')
        service.domains[u'http2'] = ('example.com',)
        self.assertTrue(service.validate(), 'nginx config is valid')

    def test_upstream_nodes(self):
        service = Service(name='test service')
        service.domains[u'http'] = ('example.com',)
        service.nodes['test_node'] = {'address': '127.0.0.1', 'port': '10000'}
        self.assertTrue(service.validate(), 'nginx config is valid')

        config = service.get_nginx_config()
        self.assertNotEqual(config.find('server 127.0.0.1:10000;'), -1, 'upstream node present')
        self.assertEqual(config.find('server 127.0.0.1:6666'), -1, 'backup node deleted')

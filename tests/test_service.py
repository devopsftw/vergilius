from mock import mock

from base_test import BaseTest
from vergilius.models.service import Service


class Test(BaseTest):
    def test_watcher(self):
        pass

    def test_base(self):
        service = Service(name='test service')
        service.flush_nginx_config()

        config_file = service.get_nginx_config_path('upstream')
        self.assertNotEqual(
                service.read_nginx_config_file('upstream').find('server 127.0.0.1:6666'),
                -1, 'config written and has backup 503')
        self.assertTrue(service.validate(), 'nginx config is valid')
        service.delete()

        with self.assertRaises(IOError):
            open(config_file, 'r')

    def test_http(self):
        service = Service(name='test service')
        service.binds['http'] = {'example.com'}

        self.assertNotEqual(
                service.get_nginx_config('http').find('server_name example.com *.example.com;'), -1,
                'server_name and wildcard present')
        self.assertTrue(service.validate(), 'nginx config is valid')

    def test_http2(self):
        service = Service(name='test service')
        service.binds['http2'] = {'example.com'}

        self.assertTrue(service.validate(), 'nginx config is valid')

    @mock.patch.object(Service, 'watch')
    def test_upstream_nodes(self, _):
        service = Service(name='test service')

        service.binds['http'] = {'example.com'}
        service.nodes['test_node'] = {'address': '127.0.0.1', 'port': '10000'}

        self.assertTrue(service.validate(), 'nginx config is valid')
        config = service.get_nginx_config('upstream')

        self.assertNotEqual(config.find('server 127.0.0.1:10000;'), -1, 'upstream node present')
        self.assertEqual(config.find('server 127.0.0.1:6666'), -1, 'backup node deleted')

    @mock.patch.object(Service, 'watch')
    def test_tcp(self, _):
        service = Service(name='test service')
        service.binds['tcp'] = {'10000'}
        service.nodes['test_node'] = {'address': '127.0.0.1', 'port': '10000'}

        self.assertTrue(service.validate(), 'nginx config is valid')
        config = service.get_nginx_config('tcp')
        self.assertNotEqual(config.find('listen %s;' % service.port), -1, 'tcp listen valid')

    @mock.patch.object(Service, 'watch')
    def test_udp(self, _):
        service = Service(name='test service')
        service.binds['udp'] = {'10000'}
        service.nodes['test_node'] = {'address': '127.0.0.1', 'port': '10000'}

        self.assertTrue(service.validate(), 'nginx config is valid')
        config = service.get_nginx_config('udp')
        self.assertNotEqual(config.find('listen %s udp;' % service.port), -1, 'udp listen valid')

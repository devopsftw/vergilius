import tornado.testing
from base_test import BaseAsyncTest, cc
from vergilius.models import Service, Certificate
from mock import mock


class CertificateTest(BaseAsyncTest):
    def setUp(self):
        super().setUp()
        cc.kv.delete('vergilius', True)

    @tornado.testing.gen_test
    def test_keys_request(self):
        service = Service('test', app=self.app)
        cert = Certificate(service, domains={'example.com'})
        yield cert.ready_event.wait()
        self.assertTrue(cert.validate(), 'got valid keys')

        with mock.patch.object(Certificate, 'request_certificate', return_value={}) as mock_method:
            Certificate(service=service, domains={'example.com'})
            self.assertFalse(mock_method.called, 'check if existing keys are not requested from provider')


class ServiceTest(BaseAsyncTest):
    def setUp(self):
        super(ServiceTest, self).setUp()
        cc.kv.delete('vergilius', True)

    def test_base(self):
        service = Service(name='test service', app=self.app)
        service.flush_nginx_config(service.get_nginx_config())

        config_file = service.get_nginx_config_path()
        self.assertNotEqual(service.read_nginx_config_file().find('server 127.0.0.1:6666'), -1,
                            'config written and has backup 503')
        self.assertTrue(service.validate(service.get_nginx_config()), 'nginx config is valid')
        service.delete()

        with self.assertRaises(IOError):
            open(config_file, 'r')

    def test_http(self):
        service = Service(name='test service', app=self.app)

        service.domains[u'http'] = ('example.com',)

        self.assertNotEqual(service.get_nginx_config().decode().find('server_name example.com *.example.com;'), -1,
                            'server_name and wildcard present')
        self.assertTrue(service.validate(service.get_nginx_config()), 'nginx config is valid')

    @tornado.testing.gen_test
    def test_http2(self):
        service = Service(name='test service', app=self.app)
        service.domains[u'http2'] = ('example.com',)
        service.certificate = Certificate(service, service.domains)
        yield service.certificate.ready_event.wait()
        self.assertTrue(service.validate(service.get_nginx_config()), 'nginx config is valid')

    def test_upstream_nodes(self):
        service = Service(name='test service', app=self.app)
        service.domains[u'http'] = ('example.com',)
        service.nodes['test_node'] = {'address': '127.0.0.1', 'port': '10000'}
        self.assertTrue(service.validate(service.get_nginx_config()), 'nginx config is valid')

        config = service.get_nginx_config().decode()
        self.assertNotEqual(config.find('server 127.0.0.1:10000;'), -1, 'upstream node present')
        self.assertEqual(config.find('server 127.0.0.1:6666'), -1, 'backup node deleted')

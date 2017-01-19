from mock import mock

from consul import Consul
from base_test import BaseTest
from vergilius.models import Certificate, Service

cc = Consul()

class Test(BaseTest):
    def __init__(self, methodName='runTest'):
        super(Test, self).__init__(methodName)
        self.service = Service('test')

    def setUp(self):
        super(Test, self).setUp()
        cc.kv.delete('vergilius', True)

    def test_keys_request(self):
        cert = Certificate(service=self.service, domains={'example.com'})
        self.assertTrue(cert.validate(), 'got valid keys')

        with mock.patch.object(Certificate, 'request_certificate', return_value={}) as mock_method:
            Certificate(service=self.service, domains={'example.com'})
            self.assertFalse(mock_method.called, 'check if existing keys are not requested from provider')

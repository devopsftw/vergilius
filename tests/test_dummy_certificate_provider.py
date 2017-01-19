from base_test import BaseTest
from vergilius.cert import DummyCertificateProvider

provider = DummyCertificateProvider()


class Test(BaseTest):
    def test_base(self):
        provider.get_certificate(domains={'example.com', 'foo.example.com'})

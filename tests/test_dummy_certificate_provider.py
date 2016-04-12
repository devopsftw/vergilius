from base_test import BaseTest
from vergilius import DummyCertificateProvider

provider = DummyCertificateProvider()


class Test(BaseTest):
    def test_base(self):
        provider.get_certificate(id='example.com|foo.example.com', domains={'example.com', 'foo.example.com'})

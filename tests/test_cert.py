import unittest
from vergilius.cert import DummyCertificateProvider


class DummyCertificateProviderTest(unittest.TestCase):
    def test_base(self):
        provider = DummyCertificateProvider()
        provider.get_certificate(domains={'example.com', 'foo.example.com'})

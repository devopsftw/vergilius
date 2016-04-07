import unittest

from src.vergilius import DummyCertificateProvider

provider = DummyCertificateProvider()


class Test(unittest.TestCase):
    def test_base(self):
        provider.get_certificate(id='example.com|foo.example.com', domains=('example.com', 'foo.example.com'))

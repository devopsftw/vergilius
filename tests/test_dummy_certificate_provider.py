import unittest

from vergilius import DummyCertificateProvider

provider = DummyCertificateProvider()


class Test(unittest.TestCase):
    def test_base(self):
        provider.gencert(id='example.com|foo.example.com', domains=('example.com', 'foo.example.com'))

import datetime
import hashlib
import os
import subprocess
import time
import zope.interface

import vergilius
from vergilius.components.certificate_provider import ICertificateProvider

OPENSSL = '/usr/bin/openssl'
KEY_SIZE = 1024
DAYS = 3650
DATA_PATH = os.path.join(vergilius.config.DATA_PATH, 'dummy_ca')
CA_CERT = os.path.join(DATA_PATH, 'ca.cert')
CA_KEY = os.path.join(DATA_PATH, 'ca.key')
X509_EXTRA_ARGS = ('-passin', 'pass:dummy')


def openssl(*args):
    cmdline = [OPENSSL] + list(args)
    if subprocess.check_call(cmdline) != 0:
        raise SystemError('Failed to run openssl', args)


class DummyCertificateProvider(object):
    """
    Issues self signed certificates.
    """
    zope.interface.implements(ICertificateProvider)

    def __init__(self):
        if not os.path.exists(DATA_PATH):
            os.mkdir(DATA_PATH)

        if not os.path.exists(os.path.join(DATA_PATH, 'domains')):
            os.mkdir(os.path.join(DATA_PATH, 'domains'))

        if not os.path.exists(os.path.join(DATA_PATH, CA_KEY)):
            vergilius.logger.info('[dummy_ca]: generating new server key')
            openssl('genrsa', '-des3', '-passout', 'pass:dummy', '-out', os.path.join(DATA_PATH, CA_KEY), '4096')

        if not os.path.exists(os.path.join(DATA_PATH, CA_CERT)):
            vergilius.logger.info('[dummy_ca]: generating new server cert')
            config = open(os.path.join(DATA_PATH, 'ca_config'), 'w')
            config.write(vergilius.template_loader.load('ca.html').generate(
                    name='dummy ca', email=vergilius.config.SSL_EMAIL
            ))
            config.close()
            openssl('req', '-new', '-x509', '-days', '3650', '-key', os.path.join(DATA_PATH, CA_KEY), '-out',
                    os.path.join(DATA_PATH, CA_CERT), '-passin', 'pass:dummy', '-config',
                    os.path.join(DATA_PATH, 'ca_config'))

    @classmethod
    def dfile(cls, id, ext):
        return os.path.join(DATA_PATH, 'domains', '%s.%s' % (id, ext))

    def get_certificate(self, id, domains, keysize=KEY_SIZE, days=DAYS, ca_cert=CA_CERT, ca_key=CA_KEY):

        if not os.path.exists(self.dfile(id, 'key')):
            openssl('genrsa', '-out', self.dfile(id, 'key'), str(keysize))

        config_file = open(self.dfile(id, 'config'), 'w')
        config_file.write(vergilius.template_loader.load('ssl.html').generate(
                domain=domains[0], dns_list=domains, email=vergilius.config.SSL_EMAIL
        ))
        config_file.close()

        openssl('req', '-new', '-key', self.dfile(id, 'key'), '-out', self.dfile(id, 'request'),
                '-config', self.dfile(id, 'config'))

        openssl('x509', '-req', '-days', str(days), '-in', self.dfile(id, 'request'),
                '-CA', ca_cert, '-CAkey', ca_key,
                '-set_serial',
                '0x%s' % hashlib.md5(domains[0] +
                                     str(datetime.datetime.now())).hexdigest(),
                '-out', self.dfile(id, 'cert'),
                '-extensions', 'v3_req', '-extfile', self.dfile(id, 'config'),
                *X509_EXTRA_ARGS)

        return {'private_key': os.path.join(DATA_PATH, self.dfile(id, 'key')),
                'public_key': os.path.join(DATA_PATH, self.dfile(id, 'cert')),
                'expires': int(time.time()) + DAYS * 24 * 60 * 60}
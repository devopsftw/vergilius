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
X509_EXTRA_ARGS = ('-passin', 'pass:%s' % vergilius.config.SECRET)


def openssl(*args):
    cmdline = [OPENSSL] + list(args)
    subprocess.check_call(cmdline)


def check_paths():
    if not os.path.exists(DATA_PATH):
        os.mkdir(DATA_PATH)

    if not os.path.exists(os.path.join(DATA_PATH, 'domains')):
        os.mkdir(os.path.join(DATA_PATH, 'domains'))


class DummyCertificateProvider(object):
    """
    Issues self signed certificates.
    """
    zope.interface.implements(ICertificateProvider)

    @classmethod
    def dfile(cls, id, ext):
        return os.path.join(DATA_PATH, 'domains', '%s.%s' % (id, ext))

    def get_certificate(self, id, domains, keysize=KEY_SIZE, days=DAYS):
        """
        :param id: string
        :type domains: set
        """
        check_paths()

        if not os.path.exists(self.dfile(id, 'key')):
            openssl('genrsa', '-out', self.dfile(id, 'key'), str(keysize))

        config_file = open(self.dfile(id, 'config'), 'w')
        config_file.write(vergilius.template_loader.load('ssl.html').generate(
                domain=sorted(list(domains))[0], dns_list=domains, email=vergilius.config.EMAIL
        ))
        config_file.close()

        openssl('req', '-new', '-key', self.dfile(id, 'key'), '-out', self.dfile(id, 'request'),
                '-config', self.dfile(id, 'config'))

        openssl('x509', '-req',
                '-days', str(days),
                '-in', self.dfile(id, 'request'),
                '-CA', vergilius.Vergilius.identity.get_certificate_path(),
                '-CAkey', vergilius.Vergilius.identity.get_private_key_path(),
                '-set_serial',
                '0x%s' % hashlib.md5(sorted(list(domains))[0] + str(datetime.datetime.now())).hexdigest(),
                '-out', self.dfile(id, 'cert'),
                '-extensions', 'v3_req',
                '-extfile', self.dfile(id, 'config'),
                *X509_EXTRA_ARGS)

        return {'private_key': os.path.join(DATA_PATH, self.dfile(id, 'key')),
                'public_key': os.path.join(DATA_PATH, self.dfile(id, 'cert')),
                'expires': int(time.time()) + DAYS * 24 * 60 * 60}

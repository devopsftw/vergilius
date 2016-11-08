import os
import subprocess
import tempfile

import vergilius

IDENTITY_PATH = os.path.join(vergilius.config.DATA_PATH, 'identity')


def openssl(*args):
    cmdline = [vergilius.config.OPENSSL_BINARY] + list(args)
    subprocess.check_call(cmdline)


class Identity(object):
    """
    Stores private keys, certificate in consul.
    Generates new identity if not specified
    """

    def __init__(self):
        self.write_files()

    def get_private_key(self):
        index, data = vergilius.consul.kv.get('vergilius/identity/private_key')
        if not data:
            return False
        else:
            return data['Value']

    def get_private_key_path(self):
        return os.path.join(IDENTITY_PATH, 'identity.key')

    def get_certificate(self):
        index, data = vergilius.consul.kv.get('vergilius/identity/certificate')
        if not data:
            self.generate_certificate()
            return self.get_certificate()
        else:
            return data['Value']

    def get_certificate_path(self):
        return os.path.join(IDENTITY_PATH, 'identity.crt')

    def generate_identity(self):
        vergilius.logger.info('[identity]: generating new identity')

        openssl('genrsa', '-des3', '-passout', 'pass:%s' % vergilius.config.SECRET, '-out', self.get_private_key_path(),
                '4096')

        private_key_file = open(self.get_private_key_path(), 'r')
        vergilius.consul.kv.put('vergilius/identity/private_key', private_key_file.read())
        private_key_file.close()

        self.get_certificate()

    def generate_certificate(self):
        ssl_config_file = tempfile.NamedTemporaryFile(delete=False)
        ssl_config_file.write(vergilius.template_loader.load('identity.html').generate(
                name='vergilius', email=vergilius.config.EMAIL
        ))
        ssl_config_file.close()

        openssl('req', '-new', '-x509', '-days', '3650', '-key', self.get_private_key_path(), '-out',
                self.get_certificate_path(), '-passin', 'pass:%s' % vergilius.config.SECRET, '-config',
                ssl_config_file.name)

        certificate_file = open(self.get_certificate_path(), 'r')
        vergilius.consul.kv.put('vergilius/identity/certificate', certificate_file.read())
        certificate_file.close()

    def write_files(self):
        if not os.path.exists(IDENTITY_PATH):
            os.mkdir(IDENTITY_PATH)

        if not self.get_private_key():
            self.generate_identity()

        private_key_file = open(self.get_private_key_path(), 'wb')
        private_key_file.write(self.get_private_key())
        private_key_file.close()

        certificate_file = open(self.get_certificate_path(), 'wb')
        certificate_file.write(self.get_certificate())
        certificate_file.close()

"""Example script showing how to use acme client API."""
import logging
from consul import Consul

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import NoEncryption

from acme import client
from acme import messages
from acme import jose

import config

logging.basicConfig(level=logging.INFO)
BITS = 4096  # minimum for Boulder


class AcmeClient(object):
    c = Consul(host=config.CONSUL_HOST)
    private_key = None
    regr = None

    def __init__(self):
        self.acme = client.Client(config.ACME_DIRECTORY_URL, jose.JWKRSA(key=self.load_private_key()))
        self.load_regr()

    def load_regr(self):
        if self.regr is None:
            index, data = self.c.kv.get('vergilius/account')
            if data:
                self.regr = messages.RegistrationResource.json_loads(data[u'Value'])
            else:
                try:
                    self.regr = self.acme.register()
                    logging.info('Auto-accepting TOS: %s', self.regr.terms_of_service)
                    self.acme.agree_to_tos(self.regr)
                    self.c.kv.put('vergilius/account', self.regr.json_dumps())
                except messages.Error as e:  # already registred
                    if e.detail != 'Registration key is already in use':
                        raise e

        return self.regr

    def load_private_key(self):
        if self.private_key is None:
            index, data = self.c.kv.get('vergilius/private_key')
            if data is None:
                logging.debug('No key in consul kv, generating new key')

                self.private_key = rsa.generate_private_key(
                        public_exponent=65537,
                        key_size=BITS,
                        backend=default_backend())

                pem = self.private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=NoEncryption()
                )
                self.c.kv.put('vergilius/private_key', pem)
            else:
                self.private_key = \
                    serialization.load_pem_private_key(data[u'Value'], password=None, backend=default_backend())

        return self.private_key

    def request_certificate(self, domains):
        for domain in domains:
            logging.info('Requesting challenge for %s' % domain)
            authzr = self.acme.request_challenges(
                    identifier=messages.Identifier(typ=messages.IDENTIFIER_FQDN, value=domain),
                    new_authzr_uri=self.regr.new_authzr_uri)
            # logging.debug(authzr)
            print("\n\n\n\n")
            print(authzr)
            print("\n\n\n\n")

            # private_key = jose.JWKRSA(key=self.private_key)
            # authzr, authzr_response = self.acme.poll(authzr)
            # csr = OpenSSL.crypto.load_certificate_request(
            #         OpenSSL.crypto.FILETYPE_ASN1, pkg_resources.resource_string(
            #                 'acme', os.path.join('testdata', 'csr.der')))
            #
            # try:
            #     self.acme.request_issuance(csr, (authzr,))
            # except messages.Error as error:
            #     print ("This script is doomed to fail as no authorization "
            #            "challenges are ever solved. Error from server: {0}".format(error))

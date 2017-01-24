import base64
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

import tornado.gen
import tornado.web
from tornado.httpclient import HTTPClient
from vergilius import config
from consul.tornado import Consul as TornadoConsul
from consul import Consul

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
import OpenSSL

from acme import client, messages, jose
import time

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)
thread_pool = ThreadPoolExecutor(4)
tc = TornadoConsul(host=config.CONSUL_HOST)


def urlsafe_b64(b):
    return base64.urlsafe_b64encode(b).decode('utf8').replace("=", "")


class AcmeCertificateProvider(object):
    cc = Consul(host=config.CONSUL_HOST)
    _acme = None
    acme_key = None

    def __init__(self):
        self.app = self.make_app()
        self.app.listen(8888)
        self.fetch_key()
        self.init_acme()

    @classmethod
    def make_app(cls):
        return tornado.web.Application([
            (r"/.well-known/acme-challenge/(.+)", AcmeChallengeHandler),
        ])

    def fetch_key(self):
        index, key_data = self.cc.kv.get('vergilius/acme/private_key')
        if key_data:
            private_key = serialization.load_pem_private_key(key_data['Value'],
                                                             password=None, backend=default_backend())
        else:
            private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                    backend=default_backend()
            )
            key_data = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
            )
            self.cc.kv.put('vergilius/acme/private_key', key_data)
        self.acme_key = jose.JWKRSA(key=private_key)

    def init_acme(self):
        self._acme = client.Client(config.ACME_DIRECTORY_URL, self.acme_key)
        try:
            regr = self._acme.register()
            self._acme.agree_to_tos(regr)
        except Exception as e:
            logger.error('acme certificate provider error: %s' % e)
            pass

    @classmethod
    def parse_token(cls, authzr):
        for c in authzr.body.challenges:
            json = c.chall.to_partial_json()
            if json['type'] == 'http-01':
                return json['token']

    def store_token(self, token):
        # put token to consul KV
        thumbprint = urlsafe_b64(self.acme_key.thumbprint())
        keyauth = '{0}.{1}'.format(token, thumbprint)
        self.cc.kv.put('vergilius/acme/challenge/%s' % token, keyauth)

    def delete_token(self, token):
        self.cc.kv.delete('vergilius/acme/challenge/%s' % token)

    def auth_domain(self, domain):
        """
        request and solve ACME challenge for domain
        :param domain: string
        :return:
        :rtype:client.messages.AuthorizationResource
        """
        # request challenges for domain
        authzr = self._acme.request_domain_challenges(domain)
        token = self.parse_token(authzr)
        self.store_token(token)

        challenge = [x for x in authzr.body.challenges if x.typ == 'http-01'][0]
        response, validation = challenge.response_and_validation(self.acme_key)
        self._acme.answer_challenge(challenge, response)

        wait_until = time.time() + 30
        while time.time() < wait_until:
            logger.debug('polling challenge result for %s' % domain)
            authzr, authzr_response = self._acme.poll(authzr)
            logger.debug('status for %s is %s' % domain, authzr.body.status)
            if authzr.body.status not in (messages.STATUS_VALID, messages.STATUS_INVALID):
                time.sleep(2)
            else:
                break
        self.delete_token(token)
        return authzr

    @classmethod
    def create_csr(cls, domains):
        """
        create private key and csr
        :param domains:
        :return: tuple with private key and csr in OpenSSL library format
        """
        private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
        )
        first_domain = domains[0]
        csr = x509.CertificateSigningRequestBuilder().subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, 'RU'),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Yekaterinburg'),
                x509.NameAttribute(NameOID.LOCALITY_NAME, 'Yekaterinburg'),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'devopsftw'),
                x509.NameAttribute(NameOID.COMMON_NAME, first_domain),
            ])
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(domain) for domain in domains
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256(), default_backend())

        csr_openssl = OpenSSL.crypto.load_certificate_request(
            OpenSSL.crypto.FILETYPE_PEM,
            csr.public_bytes(serialization.Encoding.PEM)
        )
        return private_key, csr_openssl

    def get_authzrs(self, domains):
        """request challenges for each domain"""
        authzrs = [self.auth_domain(domain) for domain in domains]
        return authzrs

    def request_certificate(self, csr, authzrs):
        """request certificates for solved challenges"""
        try:
            response = self._acme.request_issuance(jose.util.ComparableX509(csr), authzrs)
            cert_data = HTTPClient().fetch(response.uri).body
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
            return cert
        except messages.Error as error:
            print("This script is doomed to fail as no authorization "
                  "challenges are ever solved. Error from server: {0}".format(error))
        return None

    def query_letsencrypt(self, domains):
        """
        get and solve letsencrypt challenges, create CSR and request certificate for it
        :param domains:
        :return:
        """
        authzrs = self.get_authzrs(domains)
        domain_key, csr = self.create_csr(domains)
        cert = self.request_certificate(csr, authzrs)
        return domain_key, cert

    @tornado.gen.coroutine
    def get_certificate(self, domains):
        """Get certificate for requested domains"""

        logger.debug('get cert for domains %s' % domains)

        domain_key, cert = yield thread_pool.submit(self.query_letsencrypt, domains)

        if cert is None:
            return None

        key_str = domain_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        cert_str = cert.public_bytes(serialization.Encoding.PEM)
        expires = int(cert.not_valid_after.timestamp())
        result = {
            'private_key': key_str,
            'public_key': cert_str,
            'expires': expires

        }
        return result


class AcmeChallengeHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self, challenge):
        logger.debug('challenge request: %s' % challenge)
        index, data = yield tc.kv.get('vergilius/acme/challenge/%s' % challenge)
        if data:
            self.write(data['Value'])
        else:
            raise tornado.web.HTTPError(404)


class DummyCertificateProvider(object):
    @tornado.gen.coroutine
    def get_certificate(self, domains):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'RU'),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Yekaterinburg'),
            x509.NameAttribute(NameOID.LOCALITY_NAME, 'Yekaterinburg'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'devopsftw'),
            x509.NameAttribute(NameOID.COMMON_NAME, domains[0]),
        ])
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=10)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(domain) for domain in domains]),
            critical=False
        ).sign(key, hashes.SHA256(), default_backend())

        return {
            'private_key': key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ),
            'public_key': cert.public_bytes(serialization.Encoding.PEM),
            'expires': cert.not_valid_after.timestamp()
        }

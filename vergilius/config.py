import os

CONSUL_HOST = os.environ.get('CONSUL_HOST', 'localhost')
ACME_DIRECTORY_URL = os.environ.get('ACME_DIRECTORY_URL', 'https://acme-staging.api.letsencrypt.org/directory')

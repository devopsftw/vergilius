import os

CONSUL_HOST = os.environ.get('CONSUL_HOST', 'localhost')

DATA_PATH = os.environ.get('DATA_PATH', '/data/')

NGINX_CONFIG_PATH = os.environ.get('NGINX_CONFIG_PATH', '/etc/nginx/sites-enabled/')
NGINX_BINARY = os.environ.get('NGINX_BINARY', '/usr/bin/nginx')
NGINX_HTTP_PORT = os.environ.get('NGINX_HTTP_PORT', 80)
NGINX_HTTP2_PORT = os.environ.get('NGINX_HTTP2_PORT', 443)

ACME_DIRECTORY_URL = os.environ.get('ACME_DIRECTORY_URL', 'https://acme-staging.api.letsencrypt.org/directory')

SSL_EMAIL = os.environ.get('SSL_EMAIL', 'root@localhost')

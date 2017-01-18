import os

CONSUL_HOST = os.environ.get('CONSUL_HOST', 'localhost')

DATA_PATH = os.environ.get('DATA_PATH', '/data/')

NGINX_CONFIG_PATH = os.environ.get('NGINX_CONFIG_PATH', '/etc/nginx/conf.d/')
NGINX_BINARY = os.environ.get('NGINX_BINARY', '/usr/sbin/nginx')
NGINX_HTTP_PORT = os.environ.get('NGINX_HTTP_PORT', 80)
NGINX_HTTP2_PORT = os.environ.get('NGINX_HTTP2_PORT', 443)

ACME_DIRECTORY_URL = os.environ.get('ACME_DIRECTORY_URL', 'https://acme-staging.api.letsencrypt.org/directory')

EMAIL = os.environ.get('EMAIL', 'root@localhost')
SECRET = os.environ.get('SECRET')

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

if not SECRET:
    raise Exception('No secret specified!')

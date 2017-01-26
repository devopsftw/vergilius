import subprocess
from consul import tornado
from tornado.locks import Event

import vergilius

try:
    from subprocess import DEVNULL  # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')


class NginxReloader(object):
    nginx_update_event = Event()

    def __init__(self):
        pass

    @classmethod
    @tornado.gen.coroutine
    def nginx_reload(cls):
        while True:
            yield cls.nginx_update_event.wait()
            cls.nginx_update_event.clear()
            vergilius.logger.info('[nginx]: reload')
            subprocess.check_call([vergilius.config.NGINX_BINARY, '-s', 'reload'], stdout=DEVNULL)

    @classmethod
    def queue_reload(cls):
        cls.nginx_update_event.set()

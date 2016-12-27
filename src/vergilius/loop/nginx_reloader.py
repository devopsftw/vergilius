import subprocess
from consul import tornado
from tornado.ioloop import IOLoop
from tornado.locks import Event

import vergilius
from vergilius import logger


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
            try:
                subprocess.check_call([vergilius.config.NGINX_BINARY, '-s', 'reload'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                logger.error('failed to reload nginx')

    @classmethod
    def queue_reload(cls):
        cls.nginx_update_event.set()

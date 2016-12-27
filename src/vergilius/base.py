import logging
import consul

from vergilius import consul_tornado

from tornado.ioloop import IOLoop
from tornado.locks import Event
import tornado.gen

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ConsulSession(object):
    _sid = None

    def __init__(self):
        self._waitSid = Event()
        IOLoop.instance().spawn_callback(self.watch)
        pass

    @tornado.gen.coroutine
    def watch(self):
        while True:
            tick = tornado.gen.sleep(5)
            yield self.ensure_session()
            yield tick

    @tornado.gen.coroutine
    def ensure_session(self):
        if self._sid is None:
            self._sid = yield self.create_session()
            self._waitSid.set()
        else:
            try:
                yield consul_tornado.session.renew(self._sid)
            except consul.NotFound:
                logger.error('session not found, trying to recreate')
                self._sid = yield self.create_session()
            except consul.ConsulException as e:
                logger.error('consul exception: %s' % e)
        return True

    @tornado.gen.coroutine
    def create_session(self):
        sid = yield consul_tornado.session.create('vergilius', ttl=10, behavior='delete', lock_delay=0)
        logger.debug('session created: %s', sid)
        return sid

    @tornado.gen.coroutine
    def get_sid(self):
        yield self._waitSid.wait()
        return self._sid


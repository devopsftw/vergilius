#!/usr/bin/python3
import logging
import signal

import time
import tornado.ioloop

from vergilius import logger
from vergilius.loop import NginxReloader, ServiceWatcher

MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 10

logger.setLevel(logging.DEBUG)


def shutdown():
    logger.info('Stopping http server')
    tornado.ioloop.IOLoop.current().stop()

    logger.info('Will shutdown in %s seconds ...', MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
    io_loop = tornado.ioloop.IOLoop.instance()

    deadline = time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN

    def stop_loop():
        now = time.time()
        if now < deadline and (io_loop._callbacks or io_loop._timeouts):
            io_loop.add_timeout(now + 1, stop_loop)
        else:
            io_loop.stop()
            logger.info('Shutdown')

    stop_loop()


def sig_handler(sig, frame):
    logger.warning('Caught signal: %s', sig)
    tornado.ioloop.IOLoop.instance().add_callback(shutdown)


def handle_future(f):
    tornado.ioloop.IOLoop.current().stop()
    if f.exception() is not None:
        raise f.exception()


def main():
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    consul_handler = ServiceWatcher().watch_services()
    nginx_reloader = NginxReloader().nginx_reload()

    io_loop = tornado.ioloop.IOLoop.current()
    io_loop.add_future(consul_handler, handle_future)
    io_loop.add_future(nginx_reloader, handle_future)

    io_loop.start()


if __name__ == '__main__':
    main()

#!/usr/bin/python

import tornado

from loop.consul_handler import ConsulHandler
from web.main_handler import make_app

if __name__ == '__main__':
    app = make_app()
    app.listen(8888)
    consul_handler = ConsulHandler()
    tornado.ioloop.IOLoop.current().start()

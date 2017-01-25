from vergilius.config import PROXY_PORTS

allocated = set()


def allocate():
    min_port = PROXY_PORTS[0]
    max_port = PROXY_PORTS[1]

    while min_port < max_port:
        if min_port not in allocated:
            allocated.add(min_port)
            return min_port
        min_port += 1

    raise Exception('Failed to allocate port')


def release(port):
    allocated.discard(int(port))

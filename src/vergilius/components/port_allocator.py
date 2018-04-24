from vergilius.config import PROXY_PORTS
from vergilius import consul, logger

allocated = dict()


def get_ports_from_consul():
    index, ports = consul.kv.get('vergilius/ports', recurse=True)

    if ports:
        for port_data in ports:
            allocated[port_data[u'Key'].replace('vergilius/ports/', '')] = int(port_data[u'Value'])


get_ports_from_consul()


def consul_port_key(service):
    return 'vergilius/ports/%s' % service.id


def allocate(service):
    get_ports_from_consul()
    if allocated.get(service.id):
        return allocated[service.id]

    min_port = PROXY_PORTS[0]
    max_port = PROXY_PORTS[1]
    port = False

    while min_port < max_port:
        if min_port not in allocated.values():
            port = allocated[service.id] = min_port
            min_port += 1
            break
        min_port += 1

    if port:
        consul.kv.put(consul_port_key(service), str(port))
        logger.debug('[service][%s]: got allocated port %s' % (service.name, port))
        return port

    raise Exception('Failed to allocate port')


def collect_garbage(services):
    service_ids = set()
    for k, service in services.items():
        if service.port:
            service_ids.add(service.id)

    for k in allocated.keys():
        if k not in service_ids:
            del allocated[k]

    _index, consul_ports = consul.kv.get('vergilius/ports', recurse=True)

    if not consul_ports:
        return

    for port in consul_ports:
        if port[u'Key'] not in allocated.keys():
            consul.kv.delete(port[u'Key'])


def release(service):
    if allocated.get(service.id):
        try:
            del allocated[service.id]
            consul.kv.delete(consul_port_key(service))
        except Exception:
            logger.error('[service][%s]: deleting service port from consul is failed' % service.id)

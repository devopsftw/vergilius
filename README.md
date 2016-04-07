Vergilius
=========
nginx http router for docker cluster based on consul

# what is that
Docker image with nginx and tornado app, that has an opinion on how to route traffic to docker containers 
registered in consul.

# run
```bash
docker run -d -p 80:80 -p 433:433 --env-file .env --name vergilius devopsftw/vergilius
```

Example `.env` file:
```bash
CONSUL_HOST=127.0.0.1
SECRET=passw0rd
EMAIL=root@localhost
```

# how routing works

Consul service config example
```json
{
  "service": {
    "name": "my-http-service",
    "tags": [
      "http",
      "http:service.example.com",
      "http:www.service.example.com"
    ],
    "port": 8080
  }
}
```

Vergilius looks for registered services with tags `http` and `http2`, creates upstream with all containers of this service,
routes requests from `(www.)?service.example.com` and `*.(www.)?service.example.com` to containers using nginx
`least_conn` balancing algorithm.

# how http2 works

To use `http2` proxy, use `http2` tag instead of `http` or use both. Vergilius will try to acquire certificate from
plugin or create self signed certificate. 

# identity
Vergilius has an identity. To move vergilius seamlessly, copy `vergilius/identity` consul folder to your 
new cluster. If no identity found on start - it will be created for you.

- Consul key: `vergilius/identity/private_key` — private dsa3 encrypted RSA key with password specified in env `SECRET`
- Environment variable: `SECRET` - used for any encryption in vergilius

# service configuration

Additional tags: 
- `allow_crossdomain` — allow all crossdomain xhr communication for service.

# plugins

See our organisation's [repos](https://github.com/devopsftw?utf8=%E2%9C%93&query=vergilius-) for official plugins

There are [letsencrypt/acme](https://github.com/devopsftw/vergilius-acme) and 
[doorman (oauth proxy)](https://github.com/devopsftw/vergilius-doorman) integrations will be available soon. 

# TODO

- readthedocs, sphinx
- Apache Zookeeper, etcd, eureka support?

For any ideas or issues please don't hesitate to submit an issue on 
[github](https://github.com/devopsftw/vergilius/issues).
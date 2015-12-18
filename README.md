Vergilius
=========
nginx http router for docker cluster based on consul & letsencrypt

# what is that
Docker image with nginx and tornado app, that has an opinion on how to route traffic to docker containers 
registered in consul.

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

Vergilius looks for registred services with tags `http` and `http2`, creates upstream with all nodes with this service,
and routes all requests from `(www.)?service.example.com` and `*.(www.)?service.example.com` to services based on nginx
`least_conn` balancing algorithm.

# how http2 works

To use `http2` proxy, use `http2` tag instead of `http` or use both. Vergilius will try to acquire certificate from
letsencrypt and renew it automatically. To make it work you should specify `vergilius/key.pem` and 
`vergilius/contact_email` keys in your consul key/value storage.

- `vergilius/key.pem` — private RSA key with no password
- `vergilius/contact_email` — letsencrypt account email

# how to run

Fill `vergilius/key.pem` and `vergilius/contact_email` from previous section and run.

Environment variables:
- `CONSUL_HOST` - consul ip, by default - default route gateway
- `ADMIN_URL` - web interface, by default: `vergilius.dev`

# misc service tags

- `allow_crossdomain` — allow all crossdomain xhr communication for service.
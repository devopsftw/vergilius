#!/bin/sh

function die {
    echo >&2 "$@"
    exit 1
}

if [ ! -f /etc/nginx/dhparam/dhparam.pem ]; then
    mkdir -p /etc/nginx/dhparam/
    echo "dhparam file /etc/nginx/dhparam/dhparam.pem does not exist. Generating one with 4086 bit. This will take a while..."
    openssl dhparam -out /etc/nginx/dhparam/dhparam.pem 4096 || die "Could not generate dhparam file"
    echo "Finished. Starting nginx now..."
fi

exec /usr/sbin/nginx -g 'daemon off;'
#!/bin/bash

function die {
    echo >&2 "$@"
    exit 1
}

exec /opt/vergilius/app.py
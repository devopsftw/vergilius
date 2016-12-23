#!/usr/bin/env bash

if [ "$ADMIN_EMAIL" = "" ]; then
    echo "ADMIN_EMAIL is empty. Quitting.."
    exit 1
fi
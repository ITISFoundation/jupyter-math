#!/bin/bash

if [ "${DY_BOOT_OPTION_BOOT_MODE:-0}" -eq 0 ]; then
# Run the healthcheck script from the base juypyter lab image
  /etc/jupyter/docker_healthcheck.py || exit 1
else
# For voila mode, we just check if the server is running
  curl --silent --fail --output /dev/null http://localhost:8888 || exit 1
fi
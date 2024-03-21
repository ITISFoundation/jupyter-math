#/bin/sh
make .venv
source .venv/bin/activate
make install-dev
make tests-local
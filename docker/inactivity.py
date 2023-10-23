#!/home/jovyan/.venv/bin/python

# prints the result of the inactivity command

import requests

r = requests.get("http://localhost:9000")
print(r.text)
#!/home/jovyan/.venv/bin/python

# prints the result of the inactivity command

import requests

r = requests.get("http://localhost:19597")
print(r.text)
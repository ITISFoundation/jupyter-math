#!/home/jovyan/.venv/bin/python

# prints the result of the activity command

import requests

r = requests.get("http://localhost:19597")
print(r.text)
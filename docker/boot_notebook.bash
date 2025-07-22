#!/bin/bash
# SEE http://redsymbol.net/articles/unofficial-bash-strict-mode/

set -euo pipefail
IFS=$'\n\t'
INFO="INFO: [$(basename "$0")] "
WARNING="WARNING: [$(basename "$0")] "
ERROR="ERROR: [$(basename "$0")] "

echo "$INFO" "  User    :$(id "$(whoami)")"
echo "$INFO" "  Workdir :$(pwd)"

# Trust all notebooks in the notebooks folder
echo "$INFO" "trust all notebooks in path..."
find "${NOTEBOOK_BASE_DIR}" -name '*.ipynb' -type f -print0 | xargs -0 -I % /bin/bash -c 'jupyter trust "%" || true' || true

# Configure
# Prevents notebook to open in separate tab
mkdir --parents "$HOME/.jupyter/custom"
cat > "$HOME/.jupyter/custom/custom.js" <<EOF
define(['base/js/namespace'], function(Jupyter){
    Jupyter._target = '_self';
});
EOF

# SEE https://jupyter-server.readthedocs.io/en/latest/other/full-config.html
cat > .jupyter_config.json <<EOF
{
    "FileCheckpoints": {
        "checkpoint_dir": "/home/jovyan/._ipynb_checkpoints/"
    },
    "FileContentsManager": {
        "preferred_dir": "${NOTEBOOK_BASE_DIR}/workspace/"
    },
    "IdentityProvider": {
        "token": "${NOTEBOOK_TOKEN}"
    },
    "KernelSpecManager": {
        "ensure_native_kernel": false,
        "allowed_kernelspecs": ["python-maths", "octave"]
    },
    "Session": {
        "debug": false
    },
    "ServerApp": {
        "base_url": "",
        "disable_check_xsrf": true,
        "extra_static_paths": ["/static"],
        "ip": "0.0.0.0",
        "root_dir": "${NOTEBOOK_BASE_DIR}",
        "open_browser": false,
        "port": 8888,
        "quit_button": false,
        "webbrowser_open_new": 0
    }
}
EOF

# SEE https://jupyter-server.readthedocs.io/en/latest/other/full-config.html
cat > "$HOME/.jupyter/jupyter_notebook_config.py" <<EOF
c.JupyterHub.tornado_settings = {
    'cookie_options': {'SameSite': 'None', 'Secure': True}
}

c.NotebookApp.tornado_settings = {
    'cookie_options': {'SameSite': 'None', 'Secure': True}
}
c.NotebookApp.disable_check_xsrf = True
EOF

cat > "/opt/conda/share/jupyter/lab/overrides.json" <<EOF
{
     "@krassowski/jupyterlab-lsp:completion": {
        "disableCompletionsFrom": ["Kernel"],
        "kernelResponseTimeout": -1
      }
}
EOF

# shellcheck disable=SC1091
source .venv/bin/activate


#   In the future, we should have a option in the dashboard to configure how jupyter should be
#   initiated (only for the owner of the coresponding study)
VOILA_NOTEBOOK="${NOTEBOOK_BASE_DIR}"/workspace/voila.ipynb

if [ "${DY_BOOT_OPTION_BOOT_MODE}" -eq 1 ]; then
    if [ -f "${VOILA_NOTEBOOK}" ]; then
        echo "$INFO" "Found ${VOILA_NOTEBOOK}... Starting in voila mode"
        voila "${VOILA_NOTEBOOK}" --port 8888 --Voila.ip="0.0.0.0" --no-browser
    else
        echo "$ERROR" "VOILA_NOTEBOOK (${VOILA_NOTEBOOK}) not found! Cannot start in voila mode."
        exit 1
    fi
else
    # call the notebook with the basic parameters
    start-notebook.sh --config .jupyter_config.json "$@" --LabApp.default_url='/lab/tree/workspace/README.ipynb' --LabApp.collaborative=True
fi

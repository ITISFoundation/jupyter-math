ARG JUPYTER_MINIMAL_VERSION=dc9744740e12@sha256:0dc8e7bd46d7dbf27c255178ef2d92bb8ca888d32776204d19b5c23f741c1414
FROM jupyter/minimal-notebook:${JUPYTER_MINIMAL_VERSION} as service-base

# TODO: Newest image does not build well jupyterlab extensions
## ARG JUPYTER_MINIMAL_VERSION=54462805efcb@sha256:41c266e7024edd7a9efbae62c4a61527556621366c6eaad170d9c0ff6febc402

LABEL maintainer="pcrespov"

ENV JUPYTER_ENABLE_LAB="yes"
ENV NOTEBOOK_TOKEN="simcore"
ENV NOTEBOOK_BASE_DIR="$HOME/work"

USER root

# ffmpeg for matplotlib anim & dvipng for latex labels
RUN apt-get update && \
  apt-get install -y --no-install-recommends ffmpeg dvipng && \
  rm -rf /var/lib/apt/lists/*

RUN pip --no-cache --quiet install --upgrade \
  pip \
  setuptools \
  wheel

USER $NB_UID

# jupyter customizations
RUN conda install --quiet --yes \
  'jupyterlab-git~=0.20.0' \
  # https://github.com/jupyterlab/jupyterlab-latex/
  'jupyterlab_latex' \
  && \
  conda clean --all -f -y && \
  # lab extensions
  # https://github.com/jupyter-widgets/ipywidgets/tree/master/packages/jupyterlab-manager
  jupyter labextension install @jupyter-widgets/jupyterlab-manager@^2.0.0 --no-build && \
  # https://github.com/matplotlib/ipympl
  jupyter labextension install jupyter-matplotlib@^0.7.2 --no-build && \
  # https://www.npmjs.com/package/jupyterlab-plotly
  jupyter labextension install jupyterlab-plotly@^4.8.1 --no-build &&\
  # https://github.com/jupyterlab/jupyterlab-latex/
  jupyter labextension install @jupyterlab/latex@2.0.1 --no-build &&\
  # ---
  jupyter lab build -y && \
  jupyter lab clean -y && \
  npm cache clean --force && \
  rm -rf /home/$NB_USER/.cache/yarn && \
  rm -rf /home/$NB_USER/.node-gyp && \
  fix-permissions $CONDA_DIR && \
  fix-permissions /home/$NB_USER


# sidecar functionality -------------------------------------

# set up oSparc env variables
ENV INPUTS_FOLDER="${NOTEBOOK_BASE_DIR}/inputs" \
  OUTPUTS_FOLDER="${NOTEBOOK_BASE_DIR}/outputs" \
  SIMCORE_NODE_UUID="-1" \
  SIMCORE_USER_ID="-1" \
  SIMCORE_NODE_BASEPATH="" \
  SIMCORE_NODE_APP_STATE_PATH="${NOTEBOOK_BASE_DIR}" \
  STORAGE_ENDPOINT="-1" \
  S3_ENDPOINT="-1" \
  S3_ACCESS_KEY="-1" \
  S3_SECRET_KEY="-1" \
  S3_BUCKET_NAME="-1" \
  POSTGRES_ENDPOINT="-1" \
  POSTGRES_USER="-1" \
  POSTGRES_PASSWORD="-1" \
  POSTGRES_DB="-1"

# Copying boot scripts
COPY --chown=$NB_UID:$NB_GID docker /docker

# # Copying packages/common
# COPY --chown=$NB_UID:$NB_GID packages/jupyter-commons /packages/jupyter-commons
# COPY --chown=$NB_UID:$NB_GID packages/jupyter-commons/common_jupyter_notebook_config.py /home/$NB_USER/.jupyter/jupyter_notebook_config.py
# COPY --chown=$NB_UID:$NB_GID packages/jupyter-commons/state_puller.py /docker/state_puller.py

# # Installing all dependences to run handlers & remove packages
# RUN pip install /packages/jupyter-commons["jupyter-minimal"]
# USER root
# RUN rm -rf /packages
# USER $NB_UID

ENV PYTHONPATH="/src:$PYTHONPATH"
USER $NB_USER

RUN mkdir --parents --verbose "${INPUTS_FOLDER}"; \
  mkdir --parents --verbose "${OUTPUTS_FOLDER}/output_1" \
  mkdir --parents --verbose "${OUTPUTS_FOLDER}/output_2" \
  mkdir --parents --verbose "${OUTPUTS_FOLDER}/output_3" \
  mkdir --parents --verbose "${OUTPUTS_FOLDER}/output_4"

EXPOSE 8888

ENTRYPOINT [ "/bin/bash", "/docker/run.bash" ]

# --------------------------------------------------------------------
FROM service-base as service-with-kernel

# Install kernel in virtual-env
ENV HOME="/home/$NB_USER"

USER root

# TODO: [optimize] install/uninstall in single run when used only?
RUN apt-get update \
  && apt-get install -yq --no-install-recommends \
  octave \
  gnuplot \
  ghostscript \
  zip \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# NOTE: do not forget c.KernelSpecManager.ensure_native_kernel = False as well
RUN jupyter kernelspec remove -f python3  &&\
  fix-permissions /home/$NB_USER

RUN conda install --quiet --yes \
  'octave_kernel' \
  'texinfo' \
  'watchdog[watchmedo]' \
  && \
  conda clean -tipsy && \
  fix-permissions $CONDA_DIR && \
  fix-permissions /home/$NB_USER

USER $NB_UID
WORKDIR ${HOME}

RUN python3 -m venv .venv &&\
  .venv/bin/pip --no-cache --quiet install --upgrade pip wheel setuptools &&\
  .venv/bin/pip --no-cache --quiet install ipykernel &&\
  .venv/bin/python -m ipykernel install \
  --user \
  --name "python-maths" \
  --display-name "python (maths)" \
  && \
  jupyter kernelspec list

COPY --chown=$NB_UID:$NB_GID kernels/python-maths/requirements.txt ${NOTEBOOK_BASE_DIR}/requirements.txt
COPY --chown=$NB_UID:$NB_GID CHANGELOG.md ${NOTEBOOK_BASE_DIR}/CHANGELOG.md
## TODO: ensure is up-to-date before copying it

RUN .venv/bin/pip --no-cache --quiet install -r ${NOTEBOOK_BASE_DIR}/requirements.txt

# Import matplotlib the first time to build the font cache.
ENV XDG_CACHE_HOME /home/$NB_USER/.cache/
RUN MPLBACKEND=Agg .venv/bin/python -c "import matplotlib.pyplot" && \
  fix-permissions /home/$NB_USER

# Install voila parts. This may done higher up in the chain such that the other flavors also have it
RUN pip install voila
RUN jupyter serverextension enable voila --sys-prefix
RUN jupyter labextension install @jupyter-voila/jupyterlab-preview

ARG JUPYTER_MINIMAL_VERSION=lab-3.2.3@sha256:5d8ba694b92d9fe5802529b7ccf8bad23de6632d0bbaa92fc3fdc8a31cdc9c9c
FROM jupyter/minimal-notebook:${JUPYTER_MINIMAL_VERSION}

# TODO: Newest image does not build well jupyterlab extensions
## ARG JUPYTER_MINIMAL_VERSION=54462805efcb@sha256:41c266e7024edd7a9efbae62c4a61527556621366c6eaad170d9c0ff6febc402

LABEL maintainer="pcrespov"

ENV JUPYTER_ENABLE_LAB="yes"
# autentication is disabled for now
ENV NOTEBOOK_TOKEN=""
ENV NOTEBOOK_BASE_DIR="$HOME/work"

USER root

# ffmpeg for matplotlib anim & dvipng for latex labels
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  # requested by numpy compiler
  gfortran \
  ffmpeg \
  dvipng \
  # required by run.bash
  gosu \
  octave \
  gnuplot \
  ghostscript \
  zip \
  && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip --no-cache --quiet install --upgrade \
  pip \
  setuptools \
  wheel

USER $NB_UID

# jupyter customizations
RUN conda install --quiet --yes \
  'jupyterlab-git' \
  # https://github.com/jupyterlab/jupyterlab-latex/
  'jupyterlab_latex' \
  'octave_kernel' \
  'texinfo' \
  'watchdog[watchmedo]' \
  && \
  conda clean --all -f -y && \
  # Voila installation https://github.com/voila-dashboards/voila
  pip install --no-cache voila && \
  jupyter serverextension enable voila --sys-prefix && \
  # lab extensions
  # https://github.com/jupyter-widgets/ipywidgets/tree/master/packages/jupyterlab-manager
  jupyter labextension install @jupyter-widgets/jupyterlab-manager --no-build && \
  # https://github.com/matplotlib/ipympl
  jupyter labextension install jupyter-matplotlib --no-build && \
  # https://www.npmjs.com/package/jupyterlab-plotly
  jupyter labextension install jupyterlab-plotly --no-build &&\
  # https://github.com/jupyterlab/jupyterlab-latex/
  jupyter labextension install @jupyterlab/latex --no-build &&\
  # ---
  jupyter lab build -y --log-level=10 && \
  jupyter lab clean -y && \
  # ----
  npm cache clean --force && \
  rm -rf /home/$NB_USER/.cache/yarn && \
  rm -rf /home/$NB_USER/.node-gyp && \
  conda clean -tipsy && \
  fix-permissions $CONDA_DIR

# --------------------------------------------------------------------

# Install kernel in virtual-env
ENV HOME="/home/$NB_USER"

USER root

# NOTE: do not forget c.KernelSpecManager.ensure_native_kernel = False as well
RUN jupyter kernelspec remove -f python3

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

COPY --chown=$NB_UID:$NB_GID CHANGELOG.md ${NOTEBOOK_BASE_DIR}/CHANGELOG.md
# copy and resolve dependecies to be up to date
COPY --chown=$NB_UID:$NB_GID kernels/python-maths/requirements.in ${NOTEBOOK_BASE_DIR}/requirements.in
RUN .venv/bin/pip --no-cache install pip-tools && \
  .venv/bin/pip-compile --build-isolation --output-file ${NOTEBOOK_BASE_DIR}/requirements.txt ${NOTEBOOK_BASE_DIR}/requirements.in  && \
  .venv/bin/pip --no-cache install -r ${NOTEBOOK_BASE_DIR}/requirements.txt && \
  rm ${NOTEBOOK_BASE_DIR}/requirements.in

# Import matplotlib the first time to build the font cache.
ENV XDG_CACHE_HOME /home/$NB_USER/.cache/
RUN MPLBACKEND=Agg .venv/bin/python -c "import matplotlib.pyplot" && \
  # run fix permissions only once
  fix-permissions /home/$NB_USER

# Copying boot scripts
COPY --chown=$NB_UID:$NB_GID docker /docker

ENV PYTHONPATH="/src:$PYTHONPATH"

EXPOSE 8888

ENTRYPOINT [ "/bin/bash", "/docker/entrypoint.bash" ]
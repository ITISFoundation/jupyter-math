ARG JUPYTER_MINIMAL_VERSION=dc9744740e12@sha256:0dc8e7bd46d7dbf27c255178ef2d92bb8ca888d32776204d19b5c23f741c1414
FROM jupyter/minimal-notebook:${JUPYTER_MINIMAL_VERSION} as service-base

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
  # Install voila parts. This may done higher up in the chain such that the other flavors also have it
  pip install voila && \
  jupyter serverextension enable voila --sys-prefix && \
  jupyter labextension install @jupyter-voila/jupyterlab-preview --no-build && \
  # ---
  jupyter lab build -y && \
  jupyter lab clean -y && \
  npm cache clean --force && \
  rm -rf /home/$NB_USER/.cache/yarn && \
  rm -rf /home/$NB_USER/.node-gyp && \
  fix-permissions $CONDA_DIR


# --------------------------------------------------------------------
FROM service-base as service-with-kernel

# Install kernel in virtual-env
ENV HOME="/home/$NB_USER"

USER root

# TODO: [optimize] install/uninstall in single run when used only?
RUN apt-get update \
  && apt-get install -yq --no-install-recommends \
  # required by run.bash
  gosu \
  octave \
  gnuplot \
  ghostscript \
  zip \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# NOTE: do not forget c.KernelSpecManager.ensure_native_kernel = False as well
RUN jupyter kernelspec remove -f python3

RUN conda install --quiet --yes \
  'octave_kernel' \
  'texinfo' \
  'watchdog[watchmedo]' \
  && \
  conda clean -tipsy && \
  fix-permissions $CONDA_DIR


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
  # run fix permissions only once
  fix-permissions /home/$NB_USER


# Copying boot scripts
COPY --chown=$NB_UID:$NB_GID docker /docker

ENV PYTHONPATH="/src:$PYTHONPATH"

EXPOSE 8888

ENTRYPOINT [ "/bin/bash", "/docker/entrypoint.bash" ]
ARG JUPYTER_MINIMAL_VERSION=lab-3.2.9@sha256:ff1ea2df902101eda3cef853b67fa559f81a8a274416b49b0c336ac98d7436bb
FROM jupyter/minimal-notebook:${JUPYTER_MINIMAL_VERSION}


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
  texinfo \
  zip \
  fonts-freefont-otf \
  && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip --no-cache --quiet install --upgrade \
  pip \
  setuptools \
  wheel

USER $NB_UID

# --------------------------------------------------------------------

# Install kernel in virtual-env
ENV HOME="/home/$NB_USER"

USER root

# NOTE: do not forget c.KernelSpecManager.ensure_native_kernel = False as well
RUN jupyter kernelspec remove -f python3

WORKDIR ${HOME}

RUN python3 -m venv .venv &&\
  .venv/bin/pip --no-cache --quiet install --upgrade pip~=21.3 wheel setuptools &&\
  .venv/bin/pip --no-cache --quiet install ipykernel &&\
  .venv/bin/python -m ipykernel install \
  --user \
  --name "python-maths" \
  --display-name "python (maths)" \
  && \
  jupyter kernelspec list

# copy and resolve dependecies to be up to date
COPY --chown=$NB_UID:$NB_GID kernels/python-maths/requirements.in ${NOTEBOOK_BASE_DIR}/requirements.in
RUN .venv/bin/pip --no-cache install pip-tools && \
  .venv/bin/pip-compile --build-isolation --output-file ${NOTEBOOK_BASE_DIR}/requirements.txt ${NOTEBOOK_BASE_DIR}/requirements.in  && \
  .venv/bin/pip --no-cache install -r ${NOTEBOOK_BASE_DIR}/requirements.txt && \
  rm ${NOTEBOOK_BASE_DIR}/requirements.in
RUN jupyter serverextension enable voila && \
  jupyter server extension enable voila

# Import matplotlib the first time to build the font cache.
ENV XDG_CACHE_HOME /home/$NB_USER/.cache/
RUN MPLBACKEND=Agg .venv/bin/python -c "import matplotlib.pyplot" && \
  # run fix permissions only once
  fix-permissions /home/$NB_USER

# copy README and CHANGELOG
COPY --chown=$NB_UID:$NB_GID CHANGELOG.md ${NOTEBOOK_BASE_DIR}/CHANGELOG.md
COPY --chown=$NB_UID:$NB_GID README.ipynb ${NOTEBOOK_BASE_DIR}/README.ipynb
# remove write permissions from files which are not supposed to be edited
RUN chmod gu-w ${NOTEBOOK_BASE_DIR}/CHANGELOG.md && \
  chmod gu-w ${NOTEBOOK_BASE_DIR}/requirements.txt

# Copying boot scripts
COPY --chown=$NB_UID:$NB_GID docker /docker

ENV PYTHONPATH="/src:$PYTHONPATH"

EXPOSE 8888

ENTRYPOINT [ "/bin/bash", "/docker/entrypoint.bash" ]
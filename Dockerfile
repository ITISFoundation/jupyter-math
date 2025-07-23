# this is Ubuntu 24.04.2 LTS (noble)
ARG JUPYTER_MINIMAL_VERSION=lab-4.4.5@sha256:ea1adac6ee075cdadcbba6020ed5e67198814dae04d26d5d8e87417caf9f3a3d
FROM quay.io/jupyter/minimal-notebook:${JUPYTER_MINIMAL_VERSION}


LABEL maintainer="pcrespov"

ENV JUPYTER_ENABLE_LAB="yes"
# autentication is disabled for now
ENV NOTEBOOK_TOKEN=""
ENV NOTEBOOK_BASE_DIR="$HOME/work"

USER root

RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  libopenblas0 \
  gfortran \
  ffmpeg \
  make \
  dvipng \
  gosu \
  octave=8.4.0-1build5 \
  octave-dev=8.4.0-1build5 \
  gnuplot \
  bc \
  ghostscript \
  texlive-xetex \
  texlive-fonts-recommended \
  texlive-latex-recommended \
  texlive-fonts-extra \
  zip \
  fonts-freefont-otf \
  && \
  apt-get clean && rm -rf /var/lib/apt/lists/* 

RUN octave --no-window-system --eval 'pkg install "https://downloads.sourceforge.net/project/octave/Octave%20Forge%20Packages/Individual%20Package%20Releases/io-2.7.0.tar.gz"' && \
  octave --no-window-system --eval 'pkg install "https://github.com/gnu-octave/statistics/archive/refs/tags/release-1.7.4.tar.gz"' && \
  octave --no-window-system --eval 'pkg install "https://downloads.sourceforge.net/project/octave/Octave%20Forge%20Packages/Individual%20Package%20Releases/image-2.16.1.tar.gz"'

RUN pip --no-cache --quiet install --upgrade \
  pip \
  setuptools \
  wheel

USER $NB_UID

# --------------------------------------------------------------------

# Install kernel in virtual-env
ENV HOME="/home/$NB_USER"

USER root

WORKDIR ${HOME}

RUN python3 -m venv .venv &&\
  .venv/bin/pip --no-cache --quiet install --upgrade pip~=25.1 wheel setuptools &&\
  .venv/bin/pip --no-cache --quiet install ipykernel &&\
  .venv/bin/python -m ipykernel install \
  --user \
  --name "python-maths" \
  --display-name "python (maths)" \
  && \
  echo y | .venv/bin/python -m jupyter kernelspec uninstall python3 &&\
  .venv/bin/python -m jupyter kernelspec list

# copy and resolve dependencies to be up to date
COPY --chown=$NB_UID:$NB_GID kernels/python-maths/requirements.txt ${NOTEBOOK_BASE_DIR}/requirements.txt
RUN .venv/bin/pip --no-cache install pip-tools && \
  .venv/bin/pip --no-cache install -r ${NOTEBOOK_BASE_DIR}/requirements.txt

# Import matplotlib the first time to build the font cache.
ENV XDG_CACHE_HOME=/home/$NB_USER/.cache/
RUN MPLBACKEND=Agg .venv/bin/python -c "import matplotlib.pyplot" && \
  fix-permissions /home/$NB_USER
# run fix permissions only once. This can be probably optimized, so it is faster to build

# copy README and CHANGELOG
COPY --chown=$NB_UID:$NB_GID CHANGELOG.md ${NOTEBOOK_BASE_DIR}/CHANGELOG.md
COPY --chown=$NB_UID:$NB_GID README.ipynb ${NOTEBOOK_BASE_DIR}/README.ipynb
# remove write permissions from files which are not supposed to be edited
RUN chmod gu-w ${NOTEBOOK_BASE_DIR}/CHANGELOG.md && \
  chmod gu-w ${NOTEBOOK_BASE_DIR}/requirements.txt

RUN mkdir --parents "/home/${NB_USER}/.virtual_documents" && \
  chown --recursive "$NB_USER" "/home/${NB_USER}/.virtual_documents"
ENV JP_LSP_VIRTUAL_DIR="/home/${NB_USER}/.virtual_documents"


# install service activity monitor
ARG ACTIVITY_MONITOR_VERSION=v0.0.5

# Detection thresholds for application
ENV ACTIVITY_MONITOR_BUSY_THRESHOLD_CPU_PERCENT=0.5
ENV ACTIVITY_MONITOR_BUSY_THRESHOLD_DISK_READ_BPS=0
ENV ACTIVITY_MONITOR_BUSY_THRESHOLD_DISK_WRITE_BPS=0
ENV ACTIVITY_MONITOR_BUSY_THRESHOLD_NETWORK_RECEIVE_BPS=1024
ENV ACTIVITY_MONITOR_BUSY_THRESHOLD_NETWORK_SENT_BPS=1024

# install service activity monitor
RUN curl -sSL https://raw.githubusercontent.com/ITISFoundation/service-activity-monitor/main/scripts/install.sh | \
  bash -s -- ${ACTIVITY_MONITOR_VERSION}

# Copying boot scripts
COPY --chown=$NB_UID:$NB_GID docker /docker


RUN echo 'export PATH="/home/${NB_USER}/.venv/bin:$PATH"' >> "/home/${NB_USER}/.bashrc"

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 CMD [ "/docker/docker_healthcheck.bash" ]

ENTRYPOINT [ "/bin/bash", "/docker/entrypoint.bash" ]

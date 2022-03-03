# Changelog

## [2.0.5] - 2022-03-03
- changed default directory when opening to `~/work/workspace`
- fixed voila preview
- replaced readme and which is now present inside `~/work/workspace/README.ipynb`
- updated Makefile with more commands for development
- brought back octave kernel
- brought back deactivated plugins
- upgraded jupuyter-lab to v3.2.9

## [2.0.4] - 2022-02-02
- added `jupyterlab-lsp` and `python-lsp-server[all]` to make the python coding experience more user friendly

## [2.0.3] - 2022-01-28

- invalid notebooks will no longer cause the service to not start

## [2.0.2] - 2022-01-27

- changed scratch folder to workspace
- renamed default boot mode


## [2.0.1] - 2022-01-26

- changed voila to serve on 0.0.0.0 from localhost

## [2.0.0] - 2021-12-16

- updated to run via dynamic-sidecar
- output can be uploaded via the usage of symlinks
- security enhancements
- updated to python version 3.9.7
- updated to jupuyter-lab version 3.2.4

### BREAKING CHANGES:

- **inputs are currently read only**
- outputs will no longer be synced with the state of the service, these are pulled by the dynamic-sidecar before starting the service


## [1.6.13] - 2021-10-04
### Changed
- update installation of jupyter-commons with "jupyter-minimal" optional requirements

## [1.6.12] - 2021-09-01
### Fixed
- Renames service from jupyter-math to avoid character limit
- 
## [1.6.11] - 2021-08-31
### Added
- Adds voila flavor

## [1.6.10] - 2021-06-22
### Changed
- updates simcore service library to reduce cpu usage when extracting archives
## [1.6.8] - 2021-04-12
### Fixed
- updated jupyter-commons library. Should help reducing [Directory Not Found pop-up issue](https://github.com/ITISFoundation/osparc-issues/issues/412)
- Avoids empty-state [reported by control-core](https://github.com/ITISFoundation/osparc-simcore/issues/2256)

## [1.6.6] - 2021-04-06
### Fixed
- fixed simcore.service.settings docker labels concerning RAM/CPU limits

## [1.6.5] - 2021-03-22
### Fixed
- fixed requirements

## [1.6.4] - 2021-03-22
### Changed
- updated simcore-sdk to 0.3.2

## [1.6.3] - 2020-03-08
### Fixed
- state_puller no longer causes out of memory errors causing the entire app to crash
- state puller will no longer allow the notebook to boot upon error when recovering the status
### Changed
- upgraded simcore-sdk and dependencies


## [1.6.2] - 2020-02-11
### Fixed
- race condition when unarchiving
## [1.6.1] - 2021-05-02
### Changed
- work directory is archived before saving it via ports (bypasses port
  compression) should result in faster zipping
- nodeports is also using an enhanced version of archiving and unarchving

## [1.6.0] - 2021-25-01
- adds LaTeX extension which supports pdf preview for .tex files
## [Unreleased]

## [1.5.2] - 2020-18-12
- ensure empty outputs are also send to the node_ports

## [1.5.1] - 2020-15-12
- incremented dependencies to osparc-simcore libraries
- ensure output gets a .zip extension


## [1.5.0] - 2020-15-12
### Changed
- incremented dependencies to osparc-simcore libraries
- now uses node_ports_v2 package
- Improved descriptive metadata
- Fixes osparc-dependencies in jupyter-commons

## [1.4.4] - 2020-11-10
### Changed
- jupyter-commons base osparc dependency commit updated
- subfolders in outputs will now be zipped with their content
- checkpoints (not shown in the editor) have been moved to the same directory outside the ~/work.
  As a side effect, files with the same name, in different directories share the shame checkpoint.
- input and output ports raised to 4 each

## [1.4.3] - 2020-10-12
## Changed
- version bump

## [1.4.2] - 2020-09-23
## Changed
- version bump

## [1.4.1] - 2020-09-23
### Removed
- external file watcher process in jupyter-octave-python-math docker image

### Added
- file watcher attached to the Jupyter Lab runtime
- file system events are bunched together (if they are spaced at 1 second interval between events) and only trigger a single upload event
- port upload task can no longer run in parallel, they are run sequentially
- if multiple files are present in the output_X folder the .ipynb_checkpoints is removed before zipping
- installs zip (requested by reboux)

### Changed
- zip files are removed after upload

## [1.4.0] - 2020-08-26
### Added
 - pre-installs [scikit-learn](https://scikit-learn.org/stable/index.html) in python-math kernel
 - adds xlrd, xlwt and openpyxl [optional dependencies](https://pandas.pydata.org/pandas-docs/stable/getting_started/install.html#optional-dependencies) for [pandas](https://pandas.pydata.org/)

### Fixed
  - This CHANGELOG.md and requirements.txt is again visible in explorer

## [1.2.2] - 2020-07-05
### Added
- This changelog in explorer
- Python-math kernels adds [h5py](http://docs.h5py.org) and upgrades dependencies (see new [requirements.txt](requirements.txt))

### Fixed
- [#1584](https://github.com/ITISFoundation/osparc-simcore/issues/1584): Jupyterlab Math service does not render plotly
- Freezes dependencies to simcore packages and third parties. Avoids issues when changes in simcore packages


## [1.2.1] - 2020-06-24
### Changed
- Renamed to ``jupyter-octave-python-math``
- cleanup doc/icons

## [1.2.0] - 2020-05-23
### Added
- jupyter notebook with octave and python kernels
- python kernel installs math libraries (see [requirements.txt](requirements.txt))
- jupyterlab installs the following extensions:
  - [git extensions](https://github.com/jupyterlab/jupyterlab-git#readme)
  - [interactive matplotlib](https://github.com/matplotlib/ipympl#readme)


---
All notable changes to this service will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the release numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


<!-- Add links here -->

[Unreleased]:https://git.speag.com/oSparc/sparc-internal/-/compare/jopmath_v1.6.12..HEAD

[1.6.12]:https://git.speag.com/oSparc/sparc-internal/-/compare/jopmath_v1.6.12
[1.6.11]:https://git.speag.com/oSparc/sparc-internal/-/compare/jopmath_v1.6.11
[1.6.2]:https://git.speag.com/oSparc/sparc-internal/-/compare/jopmath_v1.4.0...jopmath_v1.6.2
[1.4.0]:https://git.speag.com/oSparc/sparc-internal/-/compare/jopmath_v1.2.2...jopmath_v1.4.0
[1.2.2]:https://git.speag.com/oSparc/sparc-internal/-/compare/jopmath_v1.2.1...jopmath_v1.2.2
[1.2.1]:https://git.speag.com/oSparc/sparc-internal/-/compare/jopmath_v1.2.0...jopmath_v1.2.1
[1.2.0]:https://git.speag.com/oSparc/sparc-internal/-/tags/jopmath_v1.2.0


<!-- HOW TO WRITE  THIS CHANGELOG

- Guiding Principles
  - Changelogs are for humans, not machines.
  - There should be an entry for every single version.
  - The same types of changes should be grouped.
  - Versions and sections should be linkable.
  - The latest version comes first.
  - The release date of each version is displayed.
  - Mention whether you follow Semantic Versioning.
  -
- Types of changes
  - Added for new features.
  - Changed for changes in existing functionality.
  - Deprecated for soon-to-be removed features.
  - Removed for now removed features.
  - Fixed for any bug fixes.
  - Security in case of vulnerabilities.

SEE https://keepachangelog.com/en/1.0.0/
-->


UPGRADE_OPTION := $(if $(upgrade),--upgrade-package $(upgrade),--upgrade)


requirements.txt: requirements.in
	# freezes requirements
	pip-compile $(UPGRADE_OPTION) --build-isolation --output-file $@ $<
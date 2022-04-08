# minimalistic utility to test and develop locally

SHELL = /bin/sh
.DEFAULT_GOAL := help

export DOCKER_IMAGE_NAME ?= jupyter-math
export DOCKER_IMAGE_TAG ?= 2.0.5

.PHONY: publish-local-registry
publish-local-registry:
	docker tag simcore/services/dynamic/${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG} registry:5000/simcore/services/dynamic/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)
	docker push registry:5000/simcore/services/dynamic/$(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)
	@curl registry:5000/v2/_catalog | jq

.PHONY: build
build:
	docker-compose build

.PHONY: run-local
run-local:
	docker-compose -f docker-compose-local.yml up
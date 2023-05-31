# jupyter-math


Building the docker image:

```shell
make build
```


Test the built image locally:

```shell
make run-local
```
Note that the `validation` directory will be mounted inside the service.


Raising the version can be achieved via one for three methods. The `major`,`minor` or `patch` can be bumped, for example:

```shell
make version-patch
```


If you already have a local copy of **o<sup>2</sup>S<sup>2</sup>PARC** running and wish to push data to the local registry:

```shell
make publish-local
```

### Testing manually
After a new service version has been published on the master deployment, it can be manually tested. For example a Template, called "Test Jupyter-math 2.0.9 ipywidgets" can be used for internal testing on the master deployment.

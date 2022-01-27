# Before starting

#### Directories and usage:

- `~/work/inputs` contains inputs incoming from the previous node. The contents of this folder can change at any time based on events on the platform. Even if you can write files in this folder, they will not be stored between reboots.
- `~/work/outputs` the contents of `outputs_1`, `outputs_2`, `outputs_3` and `outputs_4` will be uploaded to the platform. Files written in other positions will bot be stored between reboots.
- `~/work/workspace` is the directory where you should store your notebooks.
- `~/work/` or the current directory listed when the JupyterLab is opened. Write access to this folder has been disabled. You can only create files and directories in:
    - `~/work/workspace`
    - `~/work/outputs/outputs_1`
    - `~/work/outputs/outputs_2`
    - `~/work/outputs/outputs_3`
    - `~/work/outputs/outputs_4`

**Note:** When writing changes to one of the outputs subfolders, if more than 1 second of inactivity passes a data sync process will start in the background which will upload the content to the corresponding output port.
It is advisable to first write the data to a different directory, once all the data is written, move the contents to the output subfolder.


#### Voila mode

This notebook supports boot as voila mode. To start a notebook as voila, set the `JupyterLab` to `Voila` in the platform. Make sure to create a notebook called `voila.ipynb` in the `~/work/workspace/` directory.
Once the two above conditions are met the notebook will no longer start as JupyterLab but as Voila.

#### Have an issue?

Please open an issue on GitHub at [ITISFoundation/jupyter-math](https://github.com/ITISFoundation/jupyter-math)
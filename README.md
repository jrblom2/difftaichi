## Description
This repo is a fork off of some amazing original work by:
Yuanming Hu, Luke Anderson, Tzu-Mao Li, Qi Sun, Nathan Carr, Jonathan Ragan-Kelley, Frédo Durand

It does not contain information on difftaichi in depth, for this check out the original here:
https://github.com/taichi-dev/difftaichi

This repo has been modified to focus on the `diffmpm.py` example. The changes and enhancements focus on randomely generating chain-based creatures and evolving a population over time. The fitness for evolution is the same fitness value used to evaluate loss in gradiant decent.

The code to randomly build chain-based creatures out of blocks can be found in the custom directory inside of examples. The weights for which direction to randomly grow in can also be modified.

By defualt, an initial population will be randomely generated, the best will be selected as the parent, and generations will begin evolving from there. If no child can acheive a better loss than the parent after training, then another round begins with the same parent. All creations are saved to the `creatureDumps` direcotry for playback and visualization later.

## How to run
Step 1: Install [`Taichi`](https://github.com/taichi-dev/taichi) with `pip`:

(Most examples do **not** need a GPU to run.)
```bash
python3 -m pip install taichi
```
Step 2: Run the `diffmpm.py` file in the examples folder. The script will look for a `creatureDumps` folder in the current directory so that will have to be created first. The code contains several modifers for creature size, population size, how extreme mutations are, how long they are trained, etc. There is also a mechanism to load creature data from a directory to resume evolution from an earlier run or a specific point.
This switch can be found on line `404`

Step 3: The `diffVisualize.py` contains the original `diffmpm.py` example code to provide an easy script for visualizing a robot from the creatureDumps directory.
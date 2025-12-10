# DiscoRL: Discovering State-of-the-art Reinforcement Learning Algorithms

This repository contains accompanying code for the *"Discovering
 State-of-the-art Reinforcement Learning Algorithms"* Nature publication.

It provides a minimal JAX harness for the DiscoRL setup together with the
 original meta-learned weights for the *Disco103* discovered update rule.

The harness supports both:

-   **Meta-evaluation**: training an agent using the *Disco103* discovered RL
    update rule, using the `colabs/eval.ipynb` notebook [![Open In](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/google-deepmind/disco_rl/blob/master/colabs/eval.ipynb) and

-   **Meta-training**: meta-learning a RL update rule from scratch or from a
    pre-existing checkpoint, using the `colabs/meta_train.ipynb` notebook [![Open In](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/google-deepmind/disco_rl/blob/master/colabs/meta_train.ipynb)

Note that it will not be actively maintained moving forward.

## Installation

Set up a Python virtual environment and install the package:

```bash
python3 -m venv disco_rl_venv
source disco_rl_venv/bin/activate
pip install git+https://github.com/google-deepmind/disco_rl.git
```

The package can also be installed from colab:

```bash
!pip install git+https://github.com/google-deepmind/disco_rl.git
```

## Usage

The code is structured as follows:

* `environments/` contains the general interface for the environments that can
  be used with the provided harness, and two implementations of `Catch`:
  a CPU-based one and jittable;

* `networks/` includes a simple MLP network and LSTM-based components of the
  DiscoRL models, all implemented in Haiku;

* `update_rules/` has implementations of the discovered rules, actor-critic, and
  policy gradient;

* `value_fns/` contains value-function related utilities;

* `types.py`, `utils.py`, `optimizers.py` implement a basic functionality for
  the harness;

* `agent.py` is a generic implementation of an RL agent which uses the update
  rule's API for training, hence it is compatible with all the rules from
  `update_rules/`.

Detailed examples of usage can be found in the colabs above.

## Citation

Please cite the original Nature paper:

```
@Article{DiscoRL2025,
  author  = {Oh, Junhyuk and Farquhar, Greg and Kemaev, Iurii and Calian, Dan A. and Hessel, Matteo and Zintgraf, Luisa and Singh, Satinder and van Hasselt, Hado and Silver, David},
  journal = {Nature},
  title   = {Discovering State-of-the-art Reinforcement Learning Algorithms},
  year    = {2025},
  doi     = {10.1038/s41586-025-09761-x}
}
```

## License and disclaimer

Copyright 2025 Google LLC

All software is licensed under the Apache License, Version 2.0 (Apache 2.0);
you may not use this file except in compliance with the Apache 2.0 license.
You may obtain a copy of the Apache 2.0 license at:
https://www.apache.org/licenses/LICENSE-2.0

All other materials are licensed under the Creative Commons Attribution 4.0
International License (CC-BY). You may obtain a copy of the CC-BY license at:
https://creativecommons.org/licenses/by/4.0/legalcode

Unless required by applicable law or agreed to in writing, all software and
materials distributed here under the Apache 2.0 or CC-BY licenses are
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the licenses for the specific language governing
permissions and limitations under those licenses.

This is not an official Google product.

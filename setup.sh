#!/usr/bin/env bash

set -e

ENV_NAME=dobyte_test
PYTHON_VERSION=3.9

# ======= Remove Old Env ========
conda env remove -n $ENV_NAME -y || true
jupyter kernelspec uninstall $ENV_NAME -f || true

# ======= Create New Env ========
conda create -n $ENV_NAME python=$PYTHON_VERSION -y
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

# ======= Install project and dependencies from pyproject.toml or setup.py ========
pip install -e .

# ======= Register Jupyter Kernel ========
python -m ipykernel install --user --name $ENV_NAME --display-name "$ENV_NAME"

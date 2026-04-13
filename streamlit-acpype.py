import os
import shutil
import streamlit as st

CONDA_BIN = "/home/adminuser/.conda/bin"
CONDA_PYTHON = f"{CONDA_BIN}/python"

for p in [
    CONDA_PYTHON,
    f"{CONDA_BIN}/antechamber",
    f"{CONDA_BIN}/parmchk2",
    f"{CONDA_BIN}/tleap",
    f"{CONDA_BIN}/acpype",
]:
    st.write(p, "=>", os.path.exists(p))

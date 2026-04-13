import os
import shutil
import subprocess
import glob
import streamlit as st

st.title("AmberTools deep check")

st.subheader("1) 基本环境信息")
st.write("Python executable:", shutil.which("python"))
st.write("CONDA_PREFIX:", os.environ.get("CONDA_PREFIX"))
st.code(os.environ.get("PATH", ""))

st.subheader("2) which 检查")
for cmd in ["antechamber", "parmchk2", "tleap", "acpype"]:
    st.write(f"{cmd} => {shutil.which(cmd)}")

st.subheader("3) 直接查看常见 conda bin 目录")
bin_dir = "/home/adminuser/.conda/bin"
if os.path.isdir(bin_dir):
    hits = []
    for name in ["antechamber", "parmchk2", "tleap", "acpype"]:
        p = os.path.join(bin_dir, name)
        hits.append((name, os.path.exists(p), p))
    st.write(hits)

    try:
        ls_result = subprocess.run(
            ["bash", "-lc", f"ls -l {bin_dir} | grep -E 'antechamber|parmchk2|tleap|acpype' || true"],
            capture_output=True,
            text=True,
        )
        st.code(ls_result.stdout or "(no matches)")
    except Exception as e:
        st.exception(e)
else:
    st.error(f"{bin_dir} does not exist")

st.subheader("4) 全局 find 检查")
try:
    find_result = subprocess.run(
        [
            "bash",
            "-lc",
            "find /home/adminuser -type f \\( -name 'antechamber' -o -name 'parmchk2' -o -name 'tleap' -o -name 'acpype' \\) 2>/dev/null | sort"
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    st.code(find_result.stdout or "(nothing found)")
except Exception as e:
    st.exception(e)

st.subheader("5) conda 包信息")
try:
    conda_result = subprocess.run(
        ["bash", "-lc", "conda list | grep -E 'ambertools|acpype|openbabel|parmed' || true"],
        capture_output=True,
        text=True,
    )
    st.code(conda_result.stdout or "(no matching packages shown)")
except Exception as e:
    st.exception(e)

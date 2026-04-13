import shutil
import subprocess
import streamlit as st

st.title("AmberTools check")

for cmd in ["antechamber", "parmchk2", "tleap"]:
    st.write(cmd, "=>", shutil.which(cmd))

if shutil.which("antechamber"):
    r = subprocess.run(
        ["antechamber", "-h"],
        capture_output=True,
        text=True
    )
    st.code((r.stdout or "")[:3000] + (r.stderr or "")[:3000])
else:
    st.error("antechamber not found")

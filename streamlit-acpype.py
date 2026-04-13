import os
import subprocess
import tempfile
import zipfile
import streamlit as st

CONDA_BIN = "/home/adminuser/.conda/bin"
CONDA_PYTHON = f"{CONDA_BIN}/python"

def run_cmd(cmd, cwd=None, timeout=600):
    env = os.environ.copy()
    env["PATH"] = CONDA_BIN + ":" + env.get("PATH", "")
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )

def main():
    st.title("ACPYPE mol2 转换测试")

    st.write("Conda python exists:", os.path.exists(CONDA_PYTHON))
    st.write("ACPYPE module env:", CONDA_PYTHON)

    uploaded = st.file_uploader("上传 .mol2 文件", type=["mol2"])
    basename = st.text_input("输出前缀", value="LIG")
    net_charge = st.number_input("总电荷", value=0, step=1)
    use_user_charge = st.checkbox("使用 mol2 自带电荷 (-c user)", value=True)

    if uploaded and st.button("运行 ACPYPE"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            mol2_path = os.path.join(tmp_dir, "lig.mol2")
            with open(mol2_path, "wb") as f:
                f.write(uploaded.read())

            cmd = [
                CONDA_PYTHON,
                "-m", "acpype",
                "-i", "lig.mol2",
                "-b", basename,
                "-n", str(int(net_charge)),
            ]
            if use_user_charge:
                cmd.extend(["-c", "user"])

            st.code(" ".join(cmd))

            result = run_cmd(cmd, cwd=tmp_dir, timeout=1200)

            st.subheader("STDOUT")
            st.code(result.stdout or "(empty)")

            st.subheader("STDERR")
            st.code(result.stderr or "(empty)")

            st.write("Return code:", result.returncode)

            if result.returncode != 0:
                st.error("ACPYPE 运行失败")
                return

            st.success("ACPYPE 运行成功")

            zip_path = os.path.join(tmp_dir, "acpype_output.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(tmp_dir):
                    for file in files:
                        if file == "acpype_output.zip":
                            continue
                        full = os.path.join(root, file)
                        arcname = os.path.relpath(full, tmp_dir)
                        zipf.write(full, arcname)

            with open(zip_path, "rb") as f:
                st.download_button(
                    "下载结果 ZIP",
                    data=f.read(),
                    file_name="acpype_output.zip",
                    mime="application/zip"
                )

if __name__ == "__main__":
    main()

import os
import subprocess
import tempfile
import zipfile
import streamlit as st

CONDA_BIN = "/home/adminuser/.conda/bin"
CONDA_PYTHON = f"{CONDA_BIN}/python"
ACPYPE_EXE = f"{CONDA_BIN}/acpype"


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


def resolve_acpype_command():
    """
    返回 ACPYPE 的可执行入口。
    优先级：
    1) /home/adminuser/.conda/bin/acpype
    2) conda python + run_acpype.py
    """
    debug_lines = []

    debug_lines.append(f"CONDA_PYTHON exists: {os.path.exists(CONDA_PYTHON)}")
    debug_lines.append(f"ACPYPE_EXE exists: {os.path.exists(ACPYPE_EXE)}")

    # 方案 1：直接使用 acpype 可执行脚本
    if os.path.exists(ACPYPE_EXE):
        debug_lines.append(f"Using ACPYPE executable: {ACPYPE_EXE}")
        return [ACPYPE_EXE], "\n".join(debug_lines)

    # 方案 2：定位 acpype 包目录，寻找 run_acpype.py
    probe = run_cmd(
        [
            CONDA_PYTHON,
            "-c",
            (
                "import acpype, pathlib; "
                "pkg_dir = pathlib.Path(acpype.__file__).resolve().parent; "
                "print(pkg_dir); "
                "print(pkg_dir / 'run_acpype.py')"
            ),
        ],
        timeout=120,
    )

    debug_lines.append("Probe return code: " + str(probe.returncode))
    if probe.stdout:
        debug_lines.append("Probe stdout:\n" + probe.stdout.strip())
    if probe.stderr:
        debug_lines.append("Probe stderr:\n" + probe.stderr.strip())

    if probe.returncode != 0:
        raise RuntimeError(
            "无法导入 acpype 包并定位其目录。\n\n" + "\n".join(debug_lines)
        )

    lines = [x.strip() for x in probe.stdout.splitlines() if x.strip()]
    if len(lines) < 2:
        raise RuntimeError(
            "已导入 acpype，但未能解析出 run_acpype.py 路径。\n\n" + "\n".join(debug_lines)
        )

    pkg_dir = lines[0]
    run_script = lines[1]

    debug_lines.append(f"Resolved package dir: {pkg_dir}")
    debug_lines.append(f"Resolved run script: {run_script}")
    debug_lines.append(f"run_acpype.py exists: {os.path.exists(run_script)}")

    if os.path.exists(run_script):
        debug_lines.append(f"Using run_acpype.py via: {CONDA_PYTHON}")
        return [CONDA_PYTHON, run_script], "\n".join(debug_lines)

    raise RuntimeError(
        "未找到 ACPYPE 可执行脚本，也未找到 run_acpype.py。\n\n" + "\n".join(debug_lines)
    )


def main():
    st.title("ACPYPE mol2 Convertor")

    st.write("Conda python exists:", os.path.exists(CONDA_PYTHON))
    st.write("Conda python path:", CONDA_PYTHON)
    st.write("ACPYPE executable exists:", os.path.exists(ACPYPE_EXE))
    st.write("ACPYPE executable path:", ACPYPE_EXE)

    uploaded = st.file_uploader("上传 .mol2 文件", type=["mol2"])
    basename = st.text_input("输出前缀", value="LIG")
    net_charge = st.number_input("总电荷", value=0, step=1)
    use_user_charge = st.checkbox("使用 mol2 自带电荷 (-c user)", value=True)

    if uploaded and st.button("Run ACPYPE"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            mol2_path = os.path.join(tmp_dir, "lig.mol2")
            with open(mol2_path, "wb") as f:
                f.write(uploaded.getvalue())

            try:
                acpype_prefix, resolve_info = resolve_acpype_command()
            except Exception as e:
                st.error("Parse ACPYPE access failure")
                st.code(str(e))
                return

            st.subheader("ACPYPE access diagnosis")
            st.code(resolve_info)

            cmd = acpype_prefix + [
                "-i", "lig.mol2",
                "-b", basename,
                "-n", str(int(net_charge)),
            ]

            if use_user_charge:
                cmd.extend(["-c", "user"])

            st.subheader("实际执行命令")
            st.code(" ".join(cmd))

            try:
                result = run_cmd(cmd, cwd=tmp_dir, timeout=1200)
            except subprocess.TimeoutExpired:
                st.error("ACPYPE 运行超时")
                return
            except Exception as e:
                st.error("执行 ACPYPE 时出现异常")
                st.code(str(e))
                return

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

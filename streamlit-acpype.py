import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

CONDA_BIN = "/home/adminuser/.conda/bin"
CONDA_PYTHON = f"{CONDA_BIN}/python"
ACPYPE_EXE = f"{CONDA_BIN}/acpype"


def run_cmd(cmd, cwd=None, timeout=1200):
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


def sanitize_name(name: str, default: str = "output") -> str:
    name = (name or "").strip()
    if not name:
        return default
    name = re.sub(r"[^\w.\-]+", "_", name)
    return name or default


def resolve_acpype_command():
    """
    返回 ACPYPE 可执行入口。
    优先级：
    1) /home/adminuser/.conda/bin/acpype
    2) conda python + run_acpype.py
    """
    if os.path.exists(ACPYPE_EXE):
        return [ACPYPE_EXE]

    probe = run_cmd(
        [
            CONDA_PYTHON,
            "-c",
            (
                "import acpype, pathlib; "
                "pkg_dir = pathlib.Path(acpype.__file__).resolve().parent; "
                "print(pkg_dir / 'run_acpype.py')"
            ),
        ],
        timeout=120,
    )

    if probe.returncode != 0:
        raise RuntimeError("无法定位 ACPYPE 入口。")

    run_script = probe.stdout.strip()
    if run_script and os.path.exists(run_script):
        return [CONDA_PYTHON, run_script]

    raise RuntimeError("未找到 ACPYPE 可执行脚本。")


def resolve_obabel_command():
    """
    优先寻找 obabel，可回退到 babel。
    """
    candidates = [
        f"{CONDA_BIN}/obabel",
        f"{CONDA_BIN}/babel",
        shutil.which("obabel"),
        shutil.which("babel"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    raise RuntimeError(
        "未找到 obabel/babel 可执行文件。"
        " 若你只安装了 Python 版 openbabel 而没有 CLI，可执行文件可能不存在。"
    )


def make_zip_from_dir(src_dir: str, zip_path: str, exclude_files=None):
    exclude_files = set(exclude_files or [])
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file in exclude_files:
                    continue
                full = os.path.join(root, file)
                arcname = os.path.relpath(full, src_dir)
                zipf.write(full, arcname)


def show_logs(stdout: str, stderr: str):
    with st.expander("查看运行日志", expanded=False):
        st.subheader("STDOUT")
        st.code(stdout or "(empty)")
        st.subheader("STDERR")
        st.code(stderr or "(empty)")


def acpype_convert(uploaded, basename: str, net_charge: int, use_user_charge: bool):
    acpype_cmd = resolve_acpype_command()

    with tempfile.TemporaryDirectory() as tmp_dir:
        suffix = Path(uploaded.name).suffix.lower()
        input_name = f"input{suffix}"
        input_path = os.path.join(tmp_dir, input_name)

        with open(input_path, "wb") as f:
            f.write(uploaded.getvalue())

        cmd = acpype_cmd + [
            "-i", input_name,
            "-b", sanitize_name(basename, "LIG"),
            "-n", str(int(net_charge)),
        ]

        if use_user_charge:
            cmd.extend(["-c", "user"])

        result = run_cmd(cmd, cwd=tmp_dir, timeout=1800)

        if result.returncode != 0:
            show_logs(result.stdout, result.stderr)
            raise RuntimeError("ACPYPE 运行失败。")

        zip_path = os.path.join(tmp_dir, "acpype_output.zip")
        make_zip_from_dir(tmp_dir, zip_path, exclude_files={"acpype_output.zip"})

        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        return zip_bytes, result.stdout, result.stderr


def openbabel_convert(uploaded, input_format: str, output_format: str, output_stem: str):
    obabel_cmd = resolve_obabel_command()

    input_format = sanitize_name(input_format, "").lower().strip(".")
    output_format = sanitize_name(output_format, "").lower().strip(".")

    if not input_format:
        raise RuntimeError("请输入输入格式，例如 pdb、mol2、sdf、xyz、fasta。")
    if not output_format:
        raise RuntimeError("请输入输出格式，例如 fasta、pdb、mol2、sdf、xyz。")

    with tempfile.TemporaryDirectory() as tmp_dir:
        original_name = sanitize_name(uploaded.name, "input")
        input_path = os.path.join(tmp_dir, original_name)
        with open(input_path, "wb") as f:
            f.write(uploaded.getvalue())

        if output_stem.strip():
            stem = sanitize_name(output_stem.strip(), "converted")
        else:
            stem = sanitize_name(Path(original_name).stem, "converted")

        output_name = f"{stem}.{output_format}"
        output_path = os.path.join(tmp_dir, output_name)

        cmd = [
            obabel_cmd,
            f"-i{input_format}",
            original_name,
            "-O",
            output_name,
        ]

        result = run_cmd(cmd, cwd=tmp_dir, timeout=1200)

        if result.returncode != 0:
            show_logs(result.stdout, result.stderr)
            raise RuntimeError("Open Babel 转换失败。")

        if not os.path.exists(output_path):
            show_logs(result.stdout, result.stderr)
            raise RuntimeError("Open Babel 运行完成，但未找到输出文件。")

        with open(output_path, "rb") as f:
            out_bytes = f.read()

        return output_name, out_bytes, result.stdout, result.stderr


def main():
    st.set_page_config(page_title="ACPYPE & Open Babel Converter", layout="centered")
    st.title("ACPYPE & Open Babel Converter")

    tab1, tab2, tab3 = st.tabs(
        [
            "ACPYPE mol2",
            "ACPYPE pdb",
            "Open Babel 格式转换",
        ]
    )

    with tab1:
        st.subheader("ACPYPE mol2 转换")
        mol2_file = st.file_uploader(
            "上传 .mol2 文件",
            type=["mol2"],
            key="mol2_uploader",
        )
        mol2_basename = st.text_input("输出前缀", value="LIG", key="mol2_basename")
        mol2_charge = st.number_input("总电荷", value=0, step=1, key="mol2_charge")
        mol2_use_user_charge = st.checkbox(
            "使用 mol2 自带电荷 (-c user)",
            value=True,
            key="mol2_use_user_charge",
        )

        if st.button("运行 ACPYPE (mol2)", key="run_acpype_mol2"):
            if mol2_file is None:
                st.warning("请先上传一个 .mol2 文件。")
            else:
                try:
                    zip_bytes, stdout, stderr = acpype_convert(
                        uploaded=mol2_file,
                        basename=mol2_basename,
                        net_charge=int(mol2_charge),
                        use_user_charge=mol2_use_user_charge,
                    )
                    st.success("ACPYPE mol2 转换成功。")
                    show_logs(stdout, stderr)
                    st.download_button(
                        "下载 ACPYPE 输出 ZIP",
                        data=zip_bytes,
                        file_name="acpype_output_mol2.zip",
                        mime="application/zip",
                        key="download_mol2_zip",
                    )
                except subprocess.TimeoutExpired:
                    st.error("ACPYPE 运行超时。")
                except Exception as e:
                    st.error(str(e))

    with tab2:
        st.subheader("ACPYPE pdb 转换")
        pdb_file = st.file_uploader(
            "上传 .pdb 文件",
            type=["pdb"],
            key="pdb_uploader",
        )
        pdb_basename = st.text_input("输出前缀", value="LIG", key="pdb_basename")
        pdb_charge = st.number_input("总电荷", value=0, step=1, key="pdb_charge")

        if st.button("运行 ACPYPE (pdb)", key="run_acpype_pdb"):
            if pdb_file is None:
                st.warning("请先上传一个 .pdb 文件。")
            else:
                try:
                    zip_bytes, stdout, stderr = acpype_convert(
                        uploaded=pdb_file,
                        basename=pdb_basename,
                        net_charge=int(pdb_charge),
                        use_user_charge=False,
                    )
                    st.success("ACPYPE pdb 转换成功。")
                    show_logs(stdout, stderr)
                    st.download_button(
                        "下载 ACPYPE 输出 ZIP",
                        data=zip_bytes,
                        file_name="acpype_output_pdb.zip",
                        mime="application/zip",
                        key="download_pdb_zip",
                    )
                except subprocess.TimeoutExpired:
                    st.error("ACPYPE 运行超时。")
                except Exception as e:
                    st.error(str(e))

    with tab3:
        st.subheader("Open Babel 任意格式转换")
        any_file = st.file_uploader(
            "上传任意格式文件",
            key="obabel_uploader",
        )
        input_fmt = st.text_input(
            "输入格式（例如 pdb / mol2 / sdf / xyz / fasta）",
            value="pdb",
            key="input_fmt",
        )
        output_fmt = st.text_input(
            "输出格式（例如 fasta / pdb / mol2 / sdf / xyz）",
            value="fasta",
            key="output_fmt",
        )
        output_stem = st.text_input(
            "输出文件名（不含扩展名，可留空默认沿用原文件名）",
            value="",
            key="output_stem",
        )

        st.caption("例如：上传 eotaxin2.pdb，输入格式填 pdb，输出格式填 fasta。")

        if st.button("运行 Open Babel 转换", key="run_obabel_convert"):
            if any_file is None:
                st.warning("请先上传一个文件。")
            else:
                try:
                    output_name, out_bytes, stdout, stderr = openbabel_convert(
                        uploaded=any_file,
                        input_format=input_fmt,
                        output_format=output_fmt,
                        output_stem=output_stem,
                    )
                    st.success("Open Babel 转换成功。")
                    show_logs(stdout, stderr)
                    st.download_button(
                        "下载转换后的文件",
                        data=out_bytes,
                        file_name=output_name,
                        mime="application/octet-stream",
                        key="download_obabel_output",
                    )
                except subprocess.TimeoutExpired:
                    st.error("Open Babel 转换超时。")
                except Exception as e:
                    st.error(str(e))


if __name__ == "__main__":
    main()

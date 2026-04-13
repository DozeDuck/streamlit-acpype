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
    Return the ACPYPE execution entry point.

    Priority:
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
        raise RuntimeError("Unable to locate the ACPYPE entry point.")

    run_script = probe.stdout.strip()
    if run_script and os.path.exists(run_script):
        return [CONDA_PYTHON, run_script]

    raise RuntimeError("ACPYPE executable script was not found.")


def resolve_obabel_command():
    """
    Try to locate obabel first, then fall back to babel.
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
        "Could not find the obabel/babel executable. "
        "If only the Python Open Babel package was installed without the CLI, "
        "the executable may not be available."
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
    with st.expander("View run logs", expanded=False):
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
            raise RuntimeError("ACPYPE execution failed.")

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
        raise RuntimeError("Please provide an input format, such as pdb, mol2, sdf, xyz, or fasta.")
    if not output_format:
        raise RuntimeError("Please provide an output format, such as fasta, pdb, mol2, sdf, or xyz.")

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
            raise RuntimeError("Open Babel conversion failed.")

        if not os.path.exists(output_path):
            show_logs(result.stdout, result.stderr)
            raise RuntimeError("Open Babel finished running, but the output file was not found.")

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
            "Open Babel Format Conversion",
        ]
    )

    with tab1:
        st.subheader("ACPYPE mol2 Conversion")
        mol2_file = st.file_uploader(
            "Upload a .mol2 file",
            type=["mol2"],
            key="mol2_uploader",
        )
        mol2_basename = st.text_input("Output prefix", value="LIG", key="mol2_basename")
        mol2_charge = st.number_input("Total charge", value=0, step=1, key="mol2_charge")
        mol2_use_user_charge = st.checkbox(
            "Use charges from the mol2 file (-c user)",
            value=True,
            key="mol2_use_user_charge",
        )

        if st.button("Run ACPYPE (mol2)", key="run_acpype_mol2"):
            if mol2_file is None:
                st.warning("Please upload a .mol2 file first.")
            else:
                try:
                    zip_bytes, stdout, stderr = acpype_convert(
                        uploaded=mol2_file,
                        basename=mol2_basename,
                        net_charge=int(mol2_charge),
                        use_user_charge=mol2_use_user_charge,
                    )
                    st.success("ACPYPE mol2 conversion completed successfully.")
                    show_logs(stdout, stderr)
                    st.download_button(
                        "Download ACPYPE output ZIP",
                        data=zip_bytes,
                        file_name="acpype_output_mol2.zip",
                        mime="application/zip",
                        key="download_mol2_zip",
                    )
                except subprocess.TimeoutExpired:
                    st.error("ACPYPE execution timed out.")
                except Exception as e:
                    st.error(str(e))

    with tab2:
        st.subheader("ACPYPE pdb Conversion")
        pdb_file = st.file_uploader(
            "Upload a .pdb file",
            type=["pdb"],
            key="pdb_uploader",
        )
        pdb_basename = st.text_input("Output prefix", value="LIG", key="pdb_basename")
        pdb_charge = st.number_input("Total charge", value=0, step=1, key="pdb_charge")

        if st.button("Run ACPYPE (pdb)", key="run_acpype_pdb"):
            if pdb_file is None:
                st.warning("Please upload a .pdb file first.")
            else:
                try:
                    zip_bytes, stdout, stderr = acpype_convert(
                        uploaded=pdb_file,
                        basename=pdb_basename,
                        net_charge=int(pdb_charge),
                        use_user_charge=False,
                    )
                    st.success("ACPYPE pdb conversion completed successfully.")
                    show_logs(stdout, stderr)
                    st.download_button(
                        "Download ACPYPE output ZIP",
                        data=zip_bytes,
                        file_name="acpype_output_pdb.zip",
                        mime="application/zip",
                        key="download_pdb_zip",
                    )
                except subprocess.TimeoutExpired:
                    st.error("ACPYPE execution timed out.")
                except Exception as e:
                    st.error(str(e))

    with tab3:
        st.subheader("Open Babel Generic Format Conversion")
        any_file = st.file_uploader(
            "Upload any input file",
            key="obabel_uploader",
        )
        input_fmt = st.text_input(
            "Input format (for example: pdb / mol2 / sdf / xyz / fasta)",
            value="pdb",
            key="input_fmt",
        )
        output_fmt = st.text_input(
            "Output format (for example: fasta / pdb / mol2 / sdf / xyz)",
            value="fasta",
            key="output_fmt",
        )
        output_stem = st.text_input(
            "Output file name without extension (leave empty to reuse the original file name)",
            value="",
            key="output_stem",
        )

        st.caption("Example: upload eotaxin2.pdb, set input format to pdb, and output format to fasta.")

        if st.button("Run Open Babel Conversion", key="run_obabel_convert"):
            if any_file is None:
                st.warning("Please upload a file first.")
            else:
                try:
                    output_name, out_bytes, stdout, stderr = openbabel_convert(
                        uploaded=any_file,
                        input_format=input_fmt,
                        output_format=output_fmt,
                        output_stem=output_stem,
                    )
                    st.success("Open Babel conversion completed successfully.")
                    show_logs(stdout, stderr)
                    st.download_button(
                        "Download converted file",
                        data=out_bytes,
                        file_name=output_name,
                        mime="application/octet-stream",
                        key="download_obabel_output",
                    )
                except subprocess.TimeoutExpired:
                    st.error("Open Babel conversion timed out.")
                except Exception as e:
                    st.error(str(e))


if __name__ == "__main__":
    main()

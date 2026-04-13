import streamlit as st
import subprocess
import tempfile
import os
import zipfile

def main():
    st.title("使用 ACPYPE 转换 .mol2 文件")

    # 创建文件上传器，只接受 .mol2 格式文件
    uploaded_file = st.file_uploader("请上传 .mol2 文件", type=["mol2"])

    if uploaded_file is not None:
        # 使用临时目录保存上传的文件，避免直接写在当前工作目录
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 将上传的文件写入临时目录
            mol2_path = os.path.join(tmp_dir, "lig.mol2")
            with open(mol2_path, "wb") as f:
                f.write(uploaded_file.read())

            st.write("正在使用 ACPYPE 转换，请稍候...")

            # 执行 acpype 命令
            # 注意：本示例假设系统环境中已经安装并配置好 acpype 命令
            result = subprocess.run(["acpype", "-i", mol2_path],
                                    cwd=tmp_dir,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True)

            if result.returncode != 0:
                st.error("ACPYPE 转换出错，请检查日志：")
                st.error(result.stderr)
                return
            else:
                st.success("ACPYPE 转换完成！")

            # 为了便于用户下载，将临时目录下所有生成的文件打包成 zip
            zip_path = os.path.join(tmp_dir, "acpype_output.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(tmp_dir):
                    for file in files:
                        # 不要把自己（zip 包）也打进包里，避免死循环
                        if file != "acpype_output.zip":
                            file_full_path = os.path.join(root, file)
                            # 相对路径是为了解压后能保持目录结构
                            arcname = os.path.relpath(file_full_path, start=tmp_dir)
                            zipf.write(file_full_path, arcname=arcname)

            # 读取打包好的 zip 文件，提供下载
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="点击下载转换后的文件",
                    data=f,
                    file_name="acpype_output.zip",
                    mime="application/zip"
                )

if __name__ == "__main__":
    main()

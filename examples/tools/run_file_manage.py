from pathlib import Path
import shutil

from core.tools.file_manage.service import FileManager
from core.tools.file_manage.errors import WorkspaceViolationError


def main() -> None:
    workspace = Path("tmp_file_manage_demo")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    fm = FileManager(workspace)

    print("== 1) 创建文件 ==")
    created = fm.create_file(
        "src/hello.py",
        "def greet(name):\n    return f'hello, {name}'\n",
    )
    print("created:", created)

    print("\n== 2) 列出文件 ==")
    print(fm.list_files("."))

    print("\n== 3) 单文件 SEARCH/REPLACE 编辑 ==")
    result = fm.edit_file(
        path="src/hello.py",
        search="return f'hello, {name}'\n",
        replace="return f'hi, {name}!'\n",
    )
    print("edit result:", result)
    print("content now:\n", workspace.joinpath("src/hello.py").read_text(), sep="")

    print("\n== 4) 批量 edit-block 编辑 ==")
    instruction = """src/hello.py
<<<<<<< SEARCH
def greet(name):
    return f'hi, {name}!'
=======
def greet(name):
    message = f'hi, {name}!'
    return message
>>>>>>> REPLACE
"""
    outcomes = fm.apply_edit_blocks(instruction)
    print("block outcomes:", outcomes)
    print("content now:\n", workspace.joinpath("src/hello.py").read_text(), sep="")

    print("\n== 5) 越界写入拦截演示 ==")
    try:
        fm.create_file("../escaped.txt", "should fail\n")
    except WorkspaceViolationError as err:
        print("blocked as expected:", err)
    else:
        print("ERROR: 越界拦截失败")

    print("\nDone. 工作区目录:", workspace.resolve())


if __name__ == "__main__":
    main()

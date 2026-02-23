---
name: file_manage
description: You can do workspace-scoped file operations via this skill (create/list/edit).
entry: python -m scripts.file_manage_tool
---

# File Manage Skill Instruction

Input:
- `--workspace /abs/path`
- subcommand args

Output:
- writes only inside workspace boundary

Subcommands:

- **create** — 在 workspace 内新建文件（或覆盖已有文件）。
  - `--path <rel>`：相对 workspace 的路径，必填。
  - `--content <text>`：文件内容；不写则创建空文件。
  - `--overwrite`：若文件已存在则覆盖；不加则已存在时报错。
  - 用途：新建脚本、配置、文档等，或一次性写入整份内容。

- **list** — 列出 workspace 内文件/目录（只读，不写盘）。
  - `--base-path <rel>`：从该相对路径下开始列；不写则从 workspace 根列起。
  - `--flat`：扁平列出所有文件路径，不按目录层级缩进。
  - `--include-dirs`：在结果中同时列出目录名（默认只列文件）。
  - 用途：了解目录结构、找文件、确认路径后再做 create/edit。

- **edit** — 在已有文件内做一次“查找并替换”（就地修改）。
  - `--path <rel>`：相对 workspace 的文件路径，必填。
  - `--search <text>`：要匹配的原文（首次出现会被替换）。
  - `--replace <text>`：替换后的内容。
  - 用途：改某一行/某一段、修 typo、插入或删掉固定片段；不适合整文件重写（用 create + overwrite）。

Args examples:
- `--workspace /abs/ws create --path src/a.py --content "print('hi')\n"`
- `--workspace /abs/ws list --base-path src`
- `--workspace /abs/ws edit --path src/a.py --search "hi" --replace "hello"`

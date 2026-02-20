---
name: file_manage
description: Workspace-scoped file operations via single entry (create/list/edit/edit-blocks). Input workspace plus operation args, output JSON.
entry: python -m scripts.file_manage_tool
---

# File Manage Skill

Run workspace-scoped file operations through one CLI entry.

Input:
- `--workspace /abs/path`
- subcommand args

Output:
- JSON payload on stdout
- writes only inside workspace boundary

Subcommands:
- `create --path <rel> [--content <text>] [--overwrite]`
- `list [--base-path <rel>] [--flat] [--include-dirs] [--include-hidden]`
- `edit --path <rel> --search <text> --replace <text>`
- `edit-blocks --instruction "<EDIT_BLOCKS_TEXT>"`

Args examples:
- `--workspace /abs/ws create --path src/a.py --content "print('hi')\n"`
- `--workspace /abs/ws list --base-path src`
- `--workspace /abs/ws edit --path src/a.py --search "hi" --replace "hello"`
- `--workspace /abs/ws edit-blocks --instruction "<EDIT_BLOCKS_TEXT>"`

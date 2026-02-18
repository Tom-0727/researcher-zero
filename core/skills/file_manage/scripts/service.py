from pathlib import Path

from .create import create_file_in_workspace
from .editor import EditOutcome, apply_edit_blocks_in_workspace, edit_file_in_workspace
from .listing import list_files_in_workspace
from .workspace import WorkspaceGuard


class FileManager:
    """
    Workspace-scoped file manager for agent tools.
    Supports create/list/edit while preventing writes outside workspace.
    """

    def __init__(self, workspace_root: str | Path, encoding: str = "utf-8"):
        self.guard = WorkspaceGuard(workspace_root)
        self.encoding = encoding

    def create_file(self, path: str, content: str = "", overwrite: bool = False) -> str:
        return create_file_in_workspace(
            guard=self.guard,
            path=path,
            content=content,
            overwrite=overwrite,
            encoding=self.encoding,
        )

    def edit_file(self, path: str, search: str, replace: str) -> EditOutcome:
        return edit_file_in_workspace(
            guard=self.guard,
            path=path,
            search=search,
            replace=replace,
            encoding=self.encoding,
        )

    def apply_edit_blocks(self, instruction_text: str) -> list[EditOutcome]:
        valid_files = self.list_files(".", recursive=True, include_dirs=False, include_hidden=True)
        return apply_edit_blocks_in_workspace(
            guard=self.guard,
            instruction_text=instruction_text,
            valid_files=valid_files,
            encoding=self.encoding,
        )

    def list_files(
        self,
        base_path: str = ".",
        recursive: bool = True,
        include_dirs: bool = False,
        include_hidden: bool = False,
    ) -> list[str]:
        return list_files_in_workspace(
            guard=self.guard,
            base_path=base_path,
            recursive=recursive,
            include_dirs=include_dirs,
            include_hidden=include_hidden,
        )

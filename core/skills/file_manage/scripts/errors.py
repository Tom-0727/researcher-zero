class FileManageError(Exception):
    """Base exception for file_manage."""


class WorkspaceViolationError(FileManageError):
    """Raised when a path escapes the configured workspace."""


class FileAlreadyExistsError(FileManageError):
    """Raised when creating an existing file without overwrite."""


class EditMatchError(FileManageError):
    """Raised when SEARCH text cannot be matched in target file."""


class EditBlockParseError(FileManageError):
    """Raised when edit-block text is malformed."""

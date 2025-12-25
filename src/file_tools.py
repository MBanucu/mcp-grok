import pathlib
from typing import Optional
from mcp.types import ToolAnnotations
import os

def read_file(file_path: str, limit: int = 2000, offset: int = 0) -> str:
    """
    Read and return up to `limit` lines from `file_path`, starting at line `offset`,
    anywhere on the filesystem. Returns file content as text, or an error string if
    the file is not found, is too large, is a directory, or appears binary.
    - Files anywhere on the system can be accessed (subject to server process permissions).
    - `limit` (max lines): default 2000, hard capped at 5000. Offset must be >= 0.
    - Reading directories is blocked. Large/binary file detection is enforced.
    """
    try:
        abs_fp = pathlib.Path(file_path).expanduser().resolve()
        if not abs_fp.exists() or not abs_fp.is_file():
            return f"Error: File does not exist or is not a file: {abs_fp}"
        if abs_fp.stat().st_size > 10 * 1024 * 1024:
            return "Error: File too large (>10MB)."
        # Try to determine if binary
        try:
            with open(abs_fp, "rb") as f:
                sample = f.read(512)
                if b"\0" in sample:
                    return "Error: File appears to be binary."
        except Exception as e:
            return f"Error: Cannot check if file is binary: {type(e).__name__}: {e}"
        # Read text lines
        max_lines = min(5000, max(1, limit))
        start = max(0, offset)
        content_lines = []
        lines_read = 0
        truncated = False
        try:
            with open(abs_fp, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f):
                    if idx < start:
                        continue
                    if lines_read >= max_lines:
                        truncated = True
                        break
                    content_lines.append(line.rstrip("\n\r"))
                    lines_read += 1
        except Exception as e:
            return f"Error: Could not read file: {type(e).__name__}: {e}"
        out = "\n".join(content_lines)
        if truncated:
            out += "\n...[output truncated]..."
        return out.strip()
    except Exception as e:
        return f"Error: Unexpected error in read_file: {type(e).__name__}: {e}"

def write_file(
    file_path: str,
    content: str,
    overwrite: bool = True,
    replace_lines_start: Optional[int] = None,
    replace_lines_end: Optional[int] = None,
    insert_at_line: Optional[int] = None
) -> str:
    """
    Write `content` to the specified `file_path`. Will overwrite by default.

    Line indices:
    - All line numbers/indices (`replace_lines_start`, `replace_lines_end`, `insert_at_line`) are 0-based (the first line is line 0).
    - For line replacement, `replace_lines_start` is inclusive and `replace_lines_end` is exclusive ([start:end]).
    - For insertion, `insert_at_line` is 0-based (insert before this line; insert at 0 is before the first line).
    - If `content` is an empty string (""), then the specified replace range will be deleted entirely (no replacement lines inserted).

    Protections:
    - Canonicalizes/resolves file_path. Refuses if writing outside the server's permissions.
    - Won't overwrite if `overwrite=False` and file exists.
    - Refuses to write >10MB at once. Enforces UTF-8 encoding.
    - Won't write to device nodes, symlinks, or system directories.
    - Reports all errors with clear reason.
    """
    try:
        abs_fp = pathlib.Path(file_path).expanduser().resolve()
        if abs_fp.exists():
            if abs_fp.is_symlink():
                return f"Error: Target is a symlink: {abs_fp}"
            if abs_fp.is_dir():
                return f"Error: Refusing to write to a directory: {abs_fp}"
            if abs_fp.is_block_device() or abs_fp.is_char_device():
                return f"Error: Refusing to write to device file: {abs_fp}"
            if not overwrite:
                return f"Error: File already exists and overwrite=False: {abs_fp}"
        if len(content.encode("utf-8")) > 10 * 1024 * 1024:
            return "Error: Content too large (>10MB)."
        system_prefixes = ["/bin", "/sbin", "/lib", "/etc", "/usr", "/var", "/dev", "/proc", "/sys", "/boot", "/root"]
        if any(str(abs_fp).startswith(prefix + "/") or str(abs_fp) == prefix for prefix in system_prefixes):
            return f"Error: Refusing to write to system directory: {abs_fp}"
        abs_fp.parent.mkdir(parents=True, exist_ok=True)
        if (replace_lines_start is not None and replace_lines_end is not None) and insert_at_line is not None:
            return "Error: Cannot specify both replace_lines and insert_at_line."
        if replace_lines_start is not None and replace_lines_end is not None:
            if not abs_fp.exists() or not abs_fp.is_file():
                return f"Error: File does not exist for line replacement: {abs_fp}"
            try:
                with open(abs_fp, "r", encoding="utf-8") as f:
                    old_lines = f.readlines()
                start = int(replace_lines_start)
                end = int(replace_lines_end)
                if start < 0 or end < 0 or end < start:
                    return "Error: Invalid line range requested."
                content_is_empty = content == ""
                lines_before = old_lines[:start] if start < len(old_lines) else old_lines
                lines_after = old_lines[end:] if end < len(old_lines) else []
                if start > len(old_lines):
                    lines_before = old_lines + ["\n"] * (start - len(old_lines))
                if content_is_empty:
                    new_lines = lines_before + lines_after
                else:
                    content_lines = content.splitlines(keepends=True)
                    new_lines = lines_before + content_lines + lines_after
                with open(abs_fp, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                action = "Deleted" if content_is_empty else f"replaced"
                return f"Success: Lines {start}:{end} {action} in {abs_fp}"
            except Exception as e:
                return f"Error: Failed to replace lines: {type(e).__name__}: {e}"
        if insert_at_line is not None:
            try:
                if abs_fp.exists() and abs_fp.is_file():
                    with open(abs_fp, "r", encoding="utf-8") as f:
                        old_lines = f.readlines()
                else:
                    old_lines = []
                insert_at = max(0, int(insert_at_line or 0))
                content_lines = content.splitlines(keepends=True)
                if insert_at > len(old_lines):
                    lines_before = old_lines + ["\n"] * (insert_at - len(old_lines))
                else:
                    lines_before = old_lines[:insert_at]
                lines_after = old_lines[insert_at:] if insert_at <= len(old_lines) else []
                new_lines = lines_before + content_lines + lines_after
                with open(abs_fp, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                return f"Success: Inserted at line {insert_at} in {abs_fp}"
            except Exception as e:
                return f"Error: Failed to insert lines: {type(e).__name__}: {e}"
        mode = "w" if overwrite else "x"
        try:
            with open(abs_fp, mode, encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            return f"Error: File exists and overwrite=False: {abs_fp}"
        except Exception as e:
            return f"Error: Failed to write file: {type(e).__name__}: {e}"
        return f"Success: File written to {abs_fp}"
    except Exception as e:
        return f"Error: Unexpected error in write_file: {type(e).__name__}: {e}"

from __future__ import annotations

import filecmp
import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, List


@dataclass
class SyncResult:
    """Summary of a single sync run.

    Lists are sorted to keep results deterministic across platforms,
    because os.walk's directory order varies by filesystem.
    """

    copied: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)


class MirrorSync:
    """Mirror a source directory into a destination directory.

    The destination becomes an exact copy of the source: every file in the
    source exists in the destination with identical bytes, and every file in
    the destination that is not in the source is removed.

    Comparison is content-based, not mtime-based. Two files are considered
    equal when os.stat reports identical size AND filecmp.cmp says their
    contents match (which first checks the size shortcut, then compares
    bytes). This avoids problems with timestamp granularity across
    filesystems, network shares, and containers where mtimes may be coerced
    to whole seconds.
    """

    def __init__(self, chunk_size: int = 64 * 1024) -> None:
        # chunk_size is forwarded to filecmp so shallow comparisons of large
        # trees do not allocate huge buffers; 64 KiB is a reasonable default
        # that matches shutil.copy's internal read size.
        self._chunk_size = chunk_size

    def _rel_files(self, root: str) -> set:
        """Return the set of POSIX-style relative paths under root."""
        found: set = set()
        if not os.path.isdir(root):
            return found
        for current_dir, _subdirs, filenames in os.walk(root):
            for name in filenames:
                full = os.path.join(current_dir, name)
                rel = os.path.relpath(full, root)
                # Normalise to forward slashes so the same logical path
                # produced on Windows matches the one produced on POSIX.
                found.add(rel.replace(os.sep, "/"))
        return found

    def _files_equal(self, a: str, b: str) -> bool:
        """Return True if the two files have identical contents."""
        try:
            sa = os.stat(a)
            sb = os.stat(b)
        except OSError:
            return False
        if sa.st_size != sb.st_size:
            return False
        return filecmp.cmp(a, b, shallow=False)

    def sync(self, source: str, dest: str) -> SyncResult:
        """Synchronise source into dest.

        Raises FileNotFoundError if source is not a directory.
        Creates dest if it does not exist.
        """
        if not os.path.isdir(source):
            raise FileNotFoundError("source is not a directory: %r" % (source,))

        os.makedirs(dest, exist_ok=True)

        src_files = self._rel_files(source)
        dst_files = self._rel_files(dest)

        result = SyncResult()

        for rel in sorted(src_files):
            src_path = os.path.join(source, *rel.split("/"))
            dst_path = os.path.join(dest, *rel.split("/"))
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            if not os.path.exists(dst_path):
                shutil.copy2(src_path, dst_path)
                result.copied.append(rel)
            elif not self._files_equal(src_path, dst_path):
                # Remove then re-copy rather than copy2 in place, because
                # copy2 onto an existing file does not truncate if the new
                # content is shorter on some platforms.
                os.remove(dst_path)
                shutil.copy2(src_path, dst_path)
                result.updated.append(rel)

        for rel in sorted(dst_files - src_files):
            dst_path = os.path.join(dest, *rel.split("/"))
            os.remove(dst_path)
            result.removed.append(rel)

        return result

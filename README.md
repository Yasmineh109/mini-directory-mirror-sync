# mini-directory-mirror-sync

Mirrors a source directory into a destination directory, copying files whose contents differ and removing destination files that no longer exist in the source.

```python
import os, tempfile
from mini_directory_mirror_sync import MirrorSync

src = tempfile.mkdtemp()
dst = tempfile.mkdtemp()
with open(os.path.join(src, "hello.txt"), "w") as f:
    f.write("hello")

result = MirrorSync().sync(src, dst)
print(result.copied)   # list of relative paths newly copied
print(result.updated)   # list of relative paths whose content changed
print(result.removed)   # list of relative paths deleted from dest
```

`MirrorSync().sync(source, dest)` returns a `SyncResult` with three sorted lists of POSIX-style relative paths. The destination is created if it does not exist.

## Why this exists

The standard library offers `shutil.copytree` for one-way copies and `filecmp.dircmp` for comparison, but neither performs a true mirror: copytree does not delete files that have vanished from the source, and dircmp reports differences without acting on them. This library closes that gap in a small, dependency-free unit suitable for build steps, backup scripts, and test fixtures.

The key trade-off is comparison strategy. Timestamps are unreliable across network mounts, containers, and filesystems with coarse mtime granularity, so this library compares file contents via `filecmp.cmp(shallow=False)`. The cost is reading both files when sizes match; the benefit is correctness regardless of clock quirks.

## Edge cases

- Only regular files are tracked. Empty directories are not preserved as entries — if a source directory becomes empty of files, the corresponding destination directory is left in place rather than removed. This keeps the implementation simple and avoids surprises with permission-locked directories.
- `sync` raises `FileNotFoundError` if the source is not a directory. It does not silently no-op.
- When a file shrinks, the destination is removed and re-copied rather than overwritten in place, guaranteeing no stale trailing bytes remain.

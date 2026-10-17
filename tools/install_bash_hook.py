#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install one scoped Bash source block, preserving user settings and symlinks."""
from pathlib import Path
import argparse
import fcntl
import os
import shutil
import stat
import sys
import tempfile

BEGIN = '# >>> Astro greeting >>>'
END = '# <<< Astro greeting <<<'
BLOCK = '''# >>> Astro greeting >>>
# Only Kitty panes source Astro; other terminals are unchanged.
if [[ -n ${KITTY_WINDOW_ID-} ]]; then
    _astro_hook=${KITTY_CONFIG_DIRECTORY:-${XDG_CONFIG_HOME:-$HOME/.config}/kitty}/astro.bash
    [[ ! -r $_astro_hook ]] || source "$_astro_hook"
    unset _astro_hook
fi
# <<< Astro greeting <<<
'''


def validate_lock(info: os.stat_result, path: Path) -> None:
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        raise PermissionError(f'Unsafe Astro lock: {path}')


def private_lock(path: Path) -> int:
    """Open, but never truncate/unlink, a stable user-owned advisory lock."""
    try:
        validate_lock(path.lstat(), path)
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        validate_lock(info, path)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise OSError(f'Another Astro installation is in progress: {path}') from error
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise OSError(f'Astro lock changed while acquiring it: {path}')
        return fd
    except BaseException:
        os.close(fd)
        raise


def run_installer(source: Path, extra_args: tuple[str, ...] = ()) -> None:
    """Exec the complete installation with locks inherited by the shell."""
    home = Path.home()
    config = Path(os.environ.get('KITTY_CONFIG_DIRECTORY') or
                  Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config') / 'kitty')
    data = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
    binary = Path(os.environ.get('ASTRO_BIN_DIRECTORY') or home / '.local/bin')
    source = source.resolve()
    directories = {config.resolve(), data.resolve(), binary.resolve()}
    bashrc = Path(os.environ.get('ASTRO_BASHRC') or home / '.bashrc').resolve()
    if any(path.is_relative_to(source) for path in (*directories, bashrc)):
        raise ValueError('Installation destinations must not be inside the source checkout')
    locks = []
    try:
        # Shared data/bin roots must conflict even with different config roots.
        for directory in sorted(directories):
            directory.mkdir(parents=True, exist_ok=True)
            locks.append(private_lock(directory / '.astro-install.lock'))
        script = sys.stdin.read()
        for fd in locks:
            os.set_inheritable(fd, True)
        os.execv('/bin/sh', ['/bin/sh', '-eu', '-c', script, 'astro-install', str(source), *extra_args])
    finally:
        for fd in locks:
            os.close(fd)


def render_hook(content: str) -> str:
    lines = content.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == END]
    if not starts and not ends:
        # At EOF an unpaired backslash is literal; appending LF would instead
        # make it a continuation. Refuse rather than reinterpret user code.
        if (len(content) - len(content.rstrip('\\'))) % 2:
            raise ValueError('Ambiguous terminal backslash at EOF; add an intentional newline before installing')
        separator = '' if not content or content.endswith('\n\n') else '\n'
        return content + separator + BLOCK
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError('Ambiguous Astro hook markers; refusing to alter bashrc')
    return ''.join(lines[:starts[0]]) + BLOCK + ''.join(lines[ends[0]+1:])


def preflight_output(path: Path, source: Path | None = None) -> None:
    """Check replaceable output types and access without following file links."""
    # Replacing a leaf symlink is safe, but a symlinked parent can redirect mv
    # into the package and remove the very input the later install needs.
    destination = path.absolute().parent.resolve() / path.name
    if source is not None and destination.is_relative_to(source):
        raise ValueError(f'Output would overwrite the source checkout: {path}')
    try:
        info = path.lstat()
    except FileNotFoundError:
        info = None
    if info is not None and not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
        raise ValueError(f'Expected a file or symlink at output: {path}')
    parent = path.absolute().parent
    while True:
        try:
            parent_info = parent.stat()
            break
        except FileNotFoundError:
            parent = parent.parent
    if not stat.S_ISDIR(parent_info.st_mode) or not os.access(parent, os.W_OK | os.X_OK):
        raise PermissionError(f'Cannot write/search output parent: {parent}')
    for ancestor in parent.parents:
        if not os.access(ancestor, os.X_OK):
            raise PermissionError(f'Cannot search output ancestor: {ancestor}')
    if (info is not None and parent_info.st_mode & stat.S_ISVTX
            and os.geteuid() not in (info.st_uid, parent_info.st_uid)):
        raise PermissionError(f'Cannot replace output in sticky directory: {path}')


def hook_update(bashrc: Path) -> tuple[str, str]:
    # Read without universal-newline translation: preserve unrelated CRLF text.
    if bashrc.exists():
        if not bashrc.is_file():
            raise ValueError(f'Bash hook target must be a regular file: {bashrc}')
        with bashrc.open(encoding='utf-8', newline='') as handle:
            content = handle.read()
    else:
        content = ''
    updated = render_hook(content)
    if updated != content:
        target = bashrc.resolve()
        parent = target.parent
        while True:
            try:
                parent.stat()
                break
            except FileNotFoundError:
                parent = parent.parent
        if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
            raise PermissionError(f'Cannot atomically update Bash hook in {target.parent}')
        if target.exists() and not os.access(target, os.W_OK):
            raise PermissionError(f'Bash hook target is read-only: {target}')
        lock = target.with_name(f'.{target.name}.astro.lock')
        try:
            validate_lock(lock.lstat(), lock)
        except FileNotFoundError:
            pass
    return content, updated


def hook_snapshot(bashrc: Path):
    """Capture resolved identity and bytes; no universal-newline translation."""
    target = bashrc.resolve()
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        return target, '', None
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    with os.fdopen(fd, 'rb') as handle:
        before = identity(os.fstat(handle.fileno()))
        if not stat.S_ISREG(before[2]):
            raise ValueError(f'Bash hook target must be a regular file: {target}')
        content = handle.read().decode('utf-8')
        after = identity(os.fstat(handle.fileno()))
    if before != after or identity(target.lstat()) != after:
        raise OSError(f'Bash hook target changed concurrently: {bashrc}')
    return target, content, after


def install_hook(bashrc: Path, backup: Path) -> None:
    content, updated = hook_update(bashrc)
    if updated == content:
        return
    # Replace the resolved target, not a managed-dotfile symlink itself.
    target = bashrc.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = private_lock(target.with_name(f'.{target.name}.astro.lock'))
    temporary = None
    try:
        # Re-read under the shared target lock, including when invoked through
        # another dotfile symlink. Noncooperating editors still require a check.
        content, updated = hook_update(bashrc)
        expected = hook_snapshot(bashrc)
        if expected[0] != target or expected[1] != content:
            raise OSError(f'Bash hook target changed concurrently: {bashrc}')
        if updated == content:
            return
        mode = stat.S_IMODE(expected[2][2]) if expected[2] is not None else 0o600
        fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.astro-', dir=target.parent)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        if hook_snapshot(bashrc) != expected:
            raise OSError(f'Bash hook target changed concurrently: {bashrc}')
        if expected[2] is not None:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        if hook_snapshot(bashrc) != expected:
            raise OSError(f'Bash hook target changed concurrently: {bashrc}')
        # No filesystem CAS exists here: a noncooperating writer can still race
        # the final check/rename window. Cooperating writers hold the lock above.
        os.replace(temporary, target)
    finally:
        try:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        finally:
            os.close(lock)


def restore_hook(bashrc: Path, backup: Path) -> None:
    """Atomically restore a backed-up bashrc to its resolved target under lock."""
    try:
        info = backup.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f'Bash hook backup must be a regular file: {backup}')
    target = bashrc.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = private_lock(target.with_name(f'.{target.name}.astro.lock'))
    temporary = None
    try:
        data = backup.read_bytes()
        mode = stat.S_IMODE(info.st_mode)
        fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.astro-', dir=target.parent)
        with os.fdopen(fd, 'wb') as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        backup.unlink()
    finally:
        try:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        finally:
            os.close(lock)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--preflight']:
        try:
            source = Path(sys.argv[2]).resolve()
            for output in sys.argv[3:]:
                preflight_output(Path(output), source)
        except (OSError, ValueError) as error:
            print(f'Error: {error}. Nothing installed.', file=sys.stderr)
            raise SystemExit(1) from error
        raise SystemExit(0)
    if sys.argv[1:2] == ['--run-installer']:
        try:
            run_installer(Path(sys.argv[2]), tuple(sys.argv[3:]))
        except (OSError, ValueError) as error:
            print(f'Error: {error}. Nothing installed.', file=sys.stderr)
            raise SystemExit(1) from error
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='validate without writing')
    parser.add_argument('--restore', action='store_true', help='restore bashrc from backup')
    parser.add_argument('bashrc', type=Path)
    parser.add_argument('backup', type=Path, nargs='?')
    args = parser.parse_args()
    if not args.check and args.backup is None:
        parser.error('backup path is required unless --check is used')
    try:
        if args.check:
            hook_update(args.bashrc)
        elif args.restore:
            restore_hook(args.bashrc, args.backup)
        else:
            install_hook(args.bashrc, args.backup)
    except (OSError, ValueError) as error:
        print(f'Error: {error}', file=sys.stderr)
        raise SystemExit(1) from error

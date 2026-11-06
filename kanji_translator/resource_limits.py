"""Admission and continuous reserve checks for one owned CUDA process group.

Cleanup covers processes that remain in the owned POSIX group. SIGKILL of the
supervisor and descendants that deliberately leave that group are not covered.
"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import threading
import time

GIB = 1024**3


def snapshot():
    mem = {k: int(v.strip().split()[0])*1024 for k, v in
           (s.split(':', 1) for s in Path('/proc/meminfo').read_text().splitlines())}
    run = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, timeout=3)
    apps = subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, timeout=3)
    return dict(ram_free=mem['MemAvailable'], vram_free=int(run.stdout.strip())*1024**2,
                compute_pids=[int(x) for x in apps.stdout.splitlines() if x.strip().isdigit()])


def check(s, own_pid=None, admission=False, expected_gpu=6*GIB):
    if s['ram_free'] < 10*GIB:
        raise RuntimeError('RAM reserve below 10 GiB')
    if s['vram_free'] < 3*GIB+(expected_gpu if admission else 0):
        raise RuntimeError('VRAM reserve below 3 GiB plus admitted load')
    if any(p != own_pid for p in s['compute_pids']):
        raise RuntimeError('another GPU compute job exists')


def _live_group(pgid):
    """Linux group members still executing (or capable of executing), not zombies."""
    live = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry/'stat').read_text().rsplit(')', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        if int(fields[2]) == pgid and fields[0] not in ('Z', 'X'):
            live.append(int(entry.name))
    return live


def stop_group(child):
    """Reap the leader and terminate remaining members, even after leader exit."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic()+2
        while True:
            child.poll()  # Reap the leader without mistaking its exit for group exit.
            if not _live_group(child.pid):
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(.02)
        if not _live_group(child.pid):
            break
    child.wait(timeout=5)
    remaining = _live_group(child.pid)
    if remaining:
        raise RuntimeError('owned process group still running: '+str(remaining))


def _open_lock():
    # Fixed local path: receipt locations, TMPDIR and XDG settings cannot split it.
    directory = Path('/tmp')/('kanji-pipeline-gpu-'+str(os.getuid()))
    directory.mkdir(mode=0o700, exist_ok=True)
    dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(dfd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError('GPU lock directory must be private and owned by this user')
        fd = os.open('gpu.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=dfd)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise RuntimeError('unsafe GPU lock file')
            return os.fdopen(fd, 'a')
        except BaseException:
            os.close(fd)
            raise
    finally:
        os.close(dfd)


def _write_receipt(path, data):
    """Atomic replacement with file and directory fsync before returning."""
    fd, name = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as fh:
            json.dump(data, fh, indent=2)
            fh.write('\n')
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def _interrupts():
    # Python delivers signals to the main thread; worker threads retain caller policy.
    previous = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt('resource guard signal '+str(signum))
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGHUP):
            previous[sig] = signal.signal(sig, interrupted)
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def guarded(command, receipt, wall=55, expected_gpu=6*GIB):
    receipt = Path(receipt)
    child = first = lock = None
    start = time.monotonic()
    samples = []
    reason = cleanup_error = None
    stage = 'admission'
    # Include admission in the receipt/cleanup boundary, and retain the lock until
    # cleanup and durable receipt completion. Never unlink the shared lock inode.
    with _interrupts():
        try:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            lock = _open_lock()
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            first = snapshot()
            check(first, admission=True, expected_gpu=expected_gpu)
            stage = 'runtime'
            child = subprocess.Popen([os.sys.executable, str(Path(__file__).resolve()),
                                      str(os.getpid()), *command], start_new_session=True)
            while child.poll() is None:
                if time.monotonic()-start >= wall:
                    raise RuntimeError('owned job wall limit')
                s = snapshot()
                samples.append(s)
                check(s, child.pid)
                if time.monotonic()-start >= wall:
                    raise RuntimeError('owned job wall limit')
                time.sleep(min(.3, max(0, wall-(time.monotonic()-start))))
            if child.returncode:
                raise RuntimeError('owned GPU job exit '+str(child.returncode))
        except BaseException as error:
            reason = type(error).__name__+': '+str(error)
            raise
        finally:
            try:
                try:
                    if child is not None:
                        stop_group(child)
                except BaseException as error:
                    cleanup_error = type(error).__name__+': '+str(error)
                    if reason is None:
                        reason = cleanup_error
                    raise
                finally:
                    running = _live_group(child.pid) if child is not None else []
                    data = dict(initial=first, samples=samples, seconds=time.monotonic()-start,
                                reason=reason, stage=stage, cleanup_error=cleanup_error,
                                exit_code=child.returncode if child is not None else None,
                                owned_pid=child.pid if child is not None else None,
                                owned_process_running=bool(running), live_owned_pids=running)
                    _write_receipt(receipt, data)
            finally:
                if lock is not None:
                    lock.close()


if __name__ == '__main__':
    import ctypes
    import sys
    expected = int(sys.argv[1])
    # Linux parent-death signal covers only this direct exec child, not its tree.
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_PDEATHSIG) failed')
    if os.getppid() != expected:
        sys.exit(143)
    os.execvpe(sys.argv[2], sys.argv[2:], os.environ)

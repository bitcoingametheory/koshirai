import subprocess,sys,time
import pytest
from kanji_translator.resource_limits import GIB,check,stop_group

def test_reserve_failures():
    good=dict(ram_free=20*GIB,vram_free=10*GIB,compute_pids=[])
    check(good,admission=True)
    for changed in [dict(ram_free=9*GIB),dict(vram_free=2*GIB),dict(compute_pids=[999999])]:
        with pytest.raises(RuntimeError):check(dict(good,**changed))
    with pytest.raises(RuntimeError):check(dict(good,vram_free=8*GIB),admission=True)
    check(dict(good,compute_pids=[123]),own_pid=123)

def test_stops_actual_owned_process_ignoring_term():
    child=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(30)'],start_new_session=True,stdout=subprocess.PIPE,text=True)
    assert child.stdout.readline().strip()=='ready'
    stop_group(child)
    assert child.poll() is not None

import json,os,signal
from pathlib import Path
from kanji_translator import resource_limits as guard

GOOD=dict(ram_free=20*GIB,vram_free=10*GIB,compute_pids=[])

def test_failed_admission_durable_receipt(tmp_path,monkeypatch):
    monkeypatch.setattr(guard,'snapshot',lambda:dict(GOOD,ram_free=GIB))
    receipt=tmp_path/'failed.json'
    with pytest.raises(RuntimeError,match='RAM reserve'):
        guard.guarded([sys.executable,'-c','raise AssertionError'],receipt)
    r=json.loads(receipt.read_text())
    assert r['stage']=='admission' and r['owned_pid'] is None
    assert not r['owned_process_running'] and 'RAM reserve' in r['reason']

def test_timeout_cleans_group(tmp_path,monkeypatch):
    monkeypatch.setattr(guard,'snapshot',lambda:GOOD)
    receipt=tmp_path/'timeout.json'
    with pytest.raises(RuntimeError,match='wall limit'):
        guard.guarded([sys.executable,'-c','import time;time.sleep(30)'],receipt,wall=.3)
    r=json.loads(receipt.read_text())
    assert r['stage']=='runtime' and not r['owned_process_running']
    assert not guard._live_group(r['owned_pid'])

@pytest.mark.parametrize('leader_exits',[False,True])
def test_descendant_cleanup_after_leader_exit(tmp_path,leader_exits):
    ready=tmp_path/'ready'
    grandchild="import signal,time,os;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path("+repr(str(ready))+").write_text(str(os.getpid()));time.sleep(30)"
    script='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(grandchild)+']);'+('time.sleep(.2)' if leader_exits else 'time.sleep(30)')
    child=subprocess.Popen([sys.executable,'-c',script],start_new_session=True)
    try:
        until=time.monotonic()+5
        while not ready.exists() and time.monotonic()<until:time.sleep(.01)
        assert ready.exists()
        if leader_exits:child.wait(timeout=5)
        guard.stop_group(child)
        assert not guard._live_group(child.pid)
        pid=int(ready.read_text())
        if Path(f'/proc/{pid}/stat').exists():assert Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]=='Z'
    finally:guard.stop_group(child)

def _supervisor(tmp_path,body):
    script='from kanji_translator import resource_limits as g;g.snapshot=lambda:'+repr(GOOD)+';'+body
    return subprocess.Popen([sys.executable,'-c',script],env=dict(os.environ,PYTHONPATH=str(Path(guard.__file__).parents[1])),cwd=tmp_path,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def test_global_lock_across_receipt_directories(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir();ready=tmp_path/'ready'
    command=[sys.executable,'-c',f'from pathlib import Path;import time;Path({str(ready)!r}).touch();time.sleep(30)']
    first=_supervisor(a,f'g.guarded({command!r},"first.json",wall=20)')
    try:
        until=time.monotonic()+5
        while not ready.exists() and time.monotonic()<until:time.sleep(.01)
        assert ready.exists()
        second=_supervisor(b,'g.guarded(["false"],"second.json",wall=2)')
        assert second.wait(timeout=5)!=0
        r=json.loads((b/'second.json').read_text());assert r['stage']=='admission' and 'BlockingIOError' in r['reason']
    finally:
        first.terminate();first.wait(timeout=8)
    assert not json.loads((a/'first.json').read_text())['owned_process_running']

def test_supervisor_sigterm_cleans_descendants(tmp_path):
    ready=tmp_path/'ready'
    gc=f'import signal,time,os;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path({str(ready)!r}).write_text(str(os.getpid()));time.sleep(30)'
    command=[sys.executable,'-c',f'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",{gc!r}]);time.sleep(30)']
    parent=_supervisor(tmp_path,f'g.guarded({command!r},"receipt.json",wall=20)')
    try:
        until=time.monotonic()+5
        while not ready.exists() and time.monotonic()<until:time.sleep(.01)
        assert ready.exists();parent.send_signal(signal.SIGTERM);assert parent.wait(timeout=8)!=0
        r=json.loads((tmp_path/'receipt.json').read_text())
        assert 'signal 15' in r['reason'] and not r['owned_process_running']
        assert not guard._live_group(r['owned_pid'])
    finally:
        if parent.poll() is None:parent.terminate();parent.wait(timeout=8)

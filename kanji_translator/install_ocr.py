"""Install the pinned CPU NDLOCR reader outside the checkout, without OS changes."""
import json,subprocess,sys
from .data_paths import data_dir,external

def readiness(backend='ndl'):
    if backend!='ndl':raise ValueError('The optional Tesseract method is retired; use NDLOCR')
    from .readers.ocr.ndlocr_lite import runtime
    try:
        _,pin=runtime({})
        return {'state':'ready','backend':'ndl','engine':pin}
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        return {'state':'unavailable','backend':'ndl','reason':str(error),'next':'Run sh setup.sh --install-ocr'}

def install(backend='ndl'):
    if backend!='ndl':raise ValueError('The optional Tesseract method is retired; use NDLOCR')
    from .readers.ocr.ndlocr_lite import REVISION,UPSTREAM
    root=external(data_dir()/'ndlocr');env=root/'environment';root.mkdir(parents=True,exist_ok=True)
    python=env/'bin/python'
    if not python.exists():
        (env/'lib64').mkdir(parents=True,exist_ok=True)
        subprocess.run([sys.executable,'-m','venv','--copies',str(env)],check=True,timeout=120)
    subprocess.run([str(python),'-m','pip','install','--no-compile',UPSTREAM+'/archive/'+REVISION+'.zip'],check=True,timeout=900)
    result=readiness()
    if result['state']!='ready':raise RuntimeError(result['reason'])
    (root/'installation.json').write_text(json.dumps({'source':UPSTREAM,'revision':REVISION,'license':UPSTREAM+'/blob/'+REVISION+'/LICENCE','dependency_licenses':UPSTREAM+'/blob/'+REVISION+'/LICENCE_DEPENDENCIES',**result},indent=2)+'\n')
    return result

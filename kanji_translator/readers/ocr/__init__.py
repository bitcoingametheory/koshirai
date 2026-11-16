"""Region-selected literal OCR; engine output is a proposal, never a review."""
import csv,io,os,shutil,subprocess,tempfile
from pathlib import Path
from ...request_contracts import digest
from .ndlocr_lite import NDLOCR

def backend(config):
    language=config.get('language','auto')
    if language not in ('auto','en','ja','mixed'):raise ValueError('OCR language must be auto, en, ja or mixed')
    selected=config.get('backend','english' if language=='en' else 'ndl')
    if selected not in ('ndl','english','koten') or selected=='english' and language!='en' or selected=='koten' and (language!='ja' or config.get('script')!='historical'):
        raise ValueError('English requires language=en; Koten requires an inspected Japanese historical-script region')
    return selected

def local_engine(config):
    if backend(config)=='english':return EnglishOCR(config)
    return NDLOCR(config)

class EnglishOCR(NDLOCR):
    """English LSTM recognition with native word boxes and bounded runtime."""
    def __init__(self,config):
        binary=shutil.which(config.get('tesseract') or os.environ.get('TESSERACT','tesseract'))
        model=Path(config.get('tessdata') or os.environ.get('TESSDATA_PREFIX','/usr/share/tesseract-ocr/5/tessdata'))/'eng.traineddata'
        if not binary or not model.is_file():raise RuntimeError('Install Tesseract with eng.traineddata; set TESSERACT and TESSDATA_PREFIX')
        self.binary=binary;self.model=model;self.config=dict(config);self.ocr=None
        version=subprocess.run([binary,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.splitlines()[0]
        self.pin={'engine':'tesseract-english','version':version,'binary_sha256':digest(Path(binary).read_bytes()),
                  'model_sha256':digest(model.read_bytes()),'adapter':'english-tsv-v1','language':'eng','device':'cpu'}
        self.engine=self.pin

    def lines(self,pixels,dimensions,config):
        timeout=config.get('timeout',120);psm=config.get('psm',3)
        if not isinstance(timeout,(int,float)) or not 1<=timeout<=600 or psm not in (3,6,7,11):raise ValueError('Invalid English OCR bounds')
        with tempfile.TemporaryDirectory(prefix='english-ocr-') as folder:
            source=Path(folder)/'page.png';source.write_bytes(pixels)
            result=subprocess.run([self.binary,str(source),'stdout','--tessdata-dir',str(self.model.parent),
                '-l','eng','--oem','1','--psm',str(psm),'-c','tessedit_create_tsv=1'],
                capture_output=True,text=True,check=True,timeout=timeout,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
        width,height=dimensions;groups={};self.geometry_diagnostics=[]
        for row in csv.DictReader(io.StringIO(result.stdout),delimiter='\t',quoting=csv.QUOTE_NONE):
            if row['level']!='5' or not row['text'].strip():continue
            x,y,w,h=[int(row[k]) for k in ('left','top','width','height')];box=[x,y,x+w,y+h]
            if not (0<=x<x+w<=width and 0<=y<y+h<=height):
                self.geometry_diagnostics.append(dict(text=row['text'],original_geometry=box,geometry=None,
                    state='unresolved',reason='english_box_outside_image',coverage_eligible=False,crop_created=False));continue
            key=tuple(row[k] for k in ('page_num','block_num','par_num','line_num'))
            groups.setdefault(key,[]).append(dict(text=row['text'],box=box,confidence=float(row['conf'])))
        lines=[]
        for key,words in groups.items():
            boxes=[w['box'] for w in words]
            lines.append(dict(text=' '.join(w['text'] for w in words),box=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)],
                native_id=':'.join(key),native_block=':'.join(key[:3]),native_order=len(lines),orientation='horizontal',words=words,role='text_line'))
        self.native_layout={'blocks':[],'lines':{},'state':'native_english_line_proposals'}
        return lines

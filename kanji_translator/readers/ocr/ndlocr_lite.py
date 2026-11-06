"""NDLOCR-Lite page recognition; literal text and regions remain proposals."""
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from ...data_paths import data_dir

REVISION = 'df90b226e6f568bf0df32f12b935118d6cb74329'
UPSTREAM = 'https://github.com/ndl-lab/ndlocr-lite'
FINGERPRINT = r'''
import hashlib, importlib.metadata as m, json
d=m.distribution('ndlocr-lite')
files={}
for name in sorted(d.files or [], key=str):
    if name.suffix in ('.py','.onnx','.yaml'):
        path=d.locate_file(name)
        with path.open('rb') as stream: files[str(name)]=hashlib.file_digest(stream,'sha256').hexdigest()
if len([n for n in files if n.endswith('.onnx')]) != 4:
    raise RuntimeError('Expected four NDLOCR-Lite model files')
print(json.dumps({'engine':'NDLOCR-Lite','version':d.version,'files':files,
 'dependencies':{n:m.version(n) for n in ('onnxruntime','numpy','opencv-python-headless','pillow')}}))
'''

def runtime(config):
    python = Path(config.get('ndl_python') or os.environ.get('NDLOCR_PYTHON') or
                  data_dir() / 'ndlocr' / 'environment' / 'bin' / 'python')
    if not python.is_file():
        raise RuntimeError('NDLOCR-Lite unavailable. Run ./setup.sh --install-ocr, set NDLOCR_PYTHON, and retry.')
    try:
        result = subprocess.run([str(python), '-c', FINGERPRINT], capture_output=True,
                                text=True, check=True, timeout=30)
        pin = json.loads(result.stdout)
    except (subprocess.SubprocessError, ValueError) as error:
        raise RuntimeError('NDLOCR-Lite environment is incomplete; rerun ./setup.sh --install-ocr') from error
    pin.update(adapter='ndlocr-lite-page-v4-native-layout', device='cpu')
    return str(python), pin

class NDLOCR:
    def __init__(self, config):
        self.python, self.pin = runtime(config)

    def lines(self, pixels, dimensions, config):
        timeout = config.get('timeout', 120)
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 600:
            raise ValueError('NDLOCR timeout must be 1..600 seconds')
        with tempfile.TemporaryDirectory(prefix='kanji-ndlocr-') as folder:
            root = Path(folder); source = root / 'page.png'; source.write_bytes(pixels)
            (root / 'output').mkdir()  # Upstream returns success without OCR when absent.
            try:
                subprocess.run([self.python, '-m', 'ocr', '--sourceimg', str(source),
                                '--output', str(root / 'output'), '--device', 'cpu'],
                               check=True, capture_output=True, timeout=timeout)
                raw = json.loads((root / 'output' / 'page.json').read_text(encoding='utf-8'))
                xml_path = root / 'output' / 'page.xml'
                self.native_layout = decode_layout(xml_path.read_text(encoding='utf-8')) if xml_path.exists() else {'blocks':[], 'lines':{}, 'state':'layout_unavailable'}
            except (subprocess.SubprocessError, OSError, ValueError) as error:
                raise RuntimeError('NDLOCR-Lite execution failed: ' + type(error).__name__) from error
        self.geometry_diagnostics=[]
        lines = decode_lines(raw, dimensions, diagnostics=self.geometry_diagnostics)
        for line in lines:
            line.update(self.native_layout.get('lines',{}).get(str(line.get('native_id')),{}))
        return lines

    def prediction(self, text):
        return {'text': text, 'confidence': None, 'confidence_kind': 'not_reported',
                'unresolved': not bool(text.strip()), 'state': 'proposal',
                'accuracy_qualified': False, 'engine_pin': self.pin}

    def __call__(self, crop, region, config):
        import io
        from PIL import Image
        with Image.open(io.BytesIO(crop)) as image:
            dimensions = image.size
        return self.prediction('\n'.join(line['text'] for line in self.lines(crop, dimensions, config)))

def decode_lines(raw, dimensions, *, diagnostics=None):
    """Validate native-pixel boxes; retain upstream reading order and Unicode."""
    width, height = dimensions
    lines = []
    for group_index, group in enumerate(raw['contents']):
        for native_order,line in enumerate(group):
            points = line['boundingBox']; text = line['text']
            if not isinstance(text, str) or len(points) != 4 or any(
                len(p) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p)
                for p in points
            ): raise ValueError('Invalid NDLOCR line')
            box = [math.floor(min(p[0] for p in points)), math.floor(min(p[1] for p in points)),
                   math.ceil(max(p[0] for p in points)), math.ceil(max(p[1] for p in points))]
            box = [max(0, box[0]), max(0, box[1]), min(width, box[2]), min(height, box[3])]
            if box[2] <= box[0] or box[3] <= box[1]:
                if diagnostics is None:raise ValueError('NDLOCR box is outside the image')
                diagnostics.append({'text':text,'original_geometry':points,'state':'unresolved',
                                    'reason':'ndlocr_box_outside_image','geometry':None,
                                    'coverage_eligible':False,'crop_created':False})
                continue
            lines.append({'box': box, 'text': text,'native_id':line.get('id',native_order),
                          'native_order':native_order,'native_group':group_index,
                          'orientation':'vertical' if line.get('isVertical') in (True,'true') else 'horizontal' if line.get('isVertical') in (False,'false') else 'unknown',
                          'class_index':line.get('class_index')})
    return lines


def decode_layout(xml):
    """Retain native detector blocks, line roles and explicit block membership."""
    import xml.etree.ElementTree as ET
    root=ET.fromstring(xml);blocks=[];lines={};line_counter=[0]
    kinds={'図版':'figure','タイトル本文':'heading','キャプション':'caption','柱':'running_header','ノンブル':'page_number','表組':'table'}
    def box(element):
        if all(element.get(k) is not None for k in ('X','Y','WIDTH','HEIGHT')):
            x,y,w,h=[float(element.get(k)) for k in ('X','Y','WIDTH','HEIGHT')]
            return [x,y,x+w,y+h]
        polygon=element.find('./SHAPE/POLYGON')
        if polygon is not None:
            values=[float(v) for v in polygon.get('POINTS','').replace(',',' ').split()]
            if len(values)>=4:return [min(values[::2]),min(values[1::2]),max(values[::2]),max(values[1::2])]
        return None
    def visit(element,parent=None):
        tag=element.tag;typ=element.get('TYPE','');current=parent
        if tag in ('TEXTBLOCK','BLOCK','WARICHUBLOCK'):
            current='native-block:'+str(len(blocks))
            blocks.append({'id':current,'type':kinds.get(typ,'text_block' if tag=='TEXTBLOCK' else 'unresolved_block'),
                           'native_type':typ,'geometry':box(element),'parent_id':parent,'origin':'native_NDLOCR_detector'})
        if tag=='LINE':
            lines[str(line_counter[0])]={'native_block':parent,'role':kinds.get(typ,'text_line'),
                                         'native_type':typ,'native_reading_order':element.get('ORDER')}
            line_counter[0]+=1
        for child in element:visit(child,current)
    visit(root)
    return {'blocks':blocks,'lines':lines,'state':'native_detector_proposals'}

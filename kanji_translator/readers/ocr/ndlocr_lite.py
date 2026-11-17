"""NDLOCR-Lite page recognition; literal text and regions remain proposals."""
import json
import re
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
        self.ocr = None;self.config=dict(config);self.cwd=None
        if config.get('backend')=='koten':
            import sys
            from ...request_contracts import digest
            self.cwd=Path(config['koten_package']).resolve();self.python=config.get('koten_python',sys.executable)
            names=['model/rtmdet-s-1280x1280.onnx','model/parseq-ndl-32x384-tiny-10.onnx','config/ndl.yaml','config/NDLmoji.yaml']
            names+=sorted(str(p.relative_to(self.cwd)) for p in self.cwd.rglob('*.py'))
            self.pin=dict(engine='ndlkotenocr-lite',upstream='https://github.com/ndl-lab/ndlkotenocr-lite',
                files={name:digest((self.cwd/name).read_bytes()) for name in names},device='cpu',adapter='koten-cli-v1',accuracy_review='unreviewed')
            self.command=[self.python,'-B','-c',"import sys,runpy,onnxruntime as o; original=o.InferenceSession; options=o.SessionOptions(); options.intra_op_num_threads=1; options.inter_op_num_threads=1; o.InferenceSession=lambda *a,**k: original(*a,**dict(k,sess_options=options)); sys.argv=['ocr.py',*sys.argv[1:]]; runpy.run_path('ocr.py',run_name='__main__')"]
        elif config.get('package'):
            self._persistent_init(config['package'], config.get('device','cpu'))
            self.pin = self.engine
        else:
            self.python, self.pin = runtime(config)
            self.command=[self.python,'-B','-m','ocr']
        self.engine=self.pin

    def _persistent_init(self, package, device):
        import sys, threading
        from ...request_contracts import digest
        file_hash = lambda p: digest(p.read_bytes())
        from types import SimpleNamespace
        import onnxruntime as ort
        package = Path(package).resolve()
        ort.set_default_logger_severity(3)
        if device=='cuda':
            ort.preload_dlls()
        sys.path.append(str(package))
        import ocr
        self.ocr = ocr
        models = [package/'model/deim-s-1024x1024.onnx']
        for length in (30,50,100):
            candidates = sorted((package/'model').glob(f'*{length}-tiny*onnx'))
            if len(candidates)!=1:
                raise ValueError('Expected one installed NDL recognition model: '+str(length))
            models.append(candidates[0])
        configs = [package/'config/ndl.yaml',package/'config/NDLmoji.yaml']
        self.engine = dict(name='ndlocr-lite',version=ocr.__version__,device=device,
            onnxruntime=ort.__version__,models={p.name:file_hash(p) for p in models+configs},
            pixel_order='RGB',pdf_dpi=150,cpu_session_threads=1,concurrent_lines_per_model=1,accuracy_review='unreviewed',
            confidence_scope='NDL line confidence is detector confidence, not verified character accuracy')
        args = SimpleNamespace(det_weights=str(models[0]),det_classes=str(configs[0]),
            det_score_threshold=.2,det_conf_threshold=.25,det_iou_threshold=.2,
            device=device,rec_classes=str(configs[1]))
        self.detector = ocr.get_detector(args)
        self.recognizers = [ocr.get_recognizer(args,str(p)) for p in models[1:]]
        # Avoid four independent default CPU pools spinning while CUDA handles
        # inference. Reuse the upstream preprocessing/recognition unchanged.
        options=ort.SessionOptions()
        options.intra_op_num_threads=1
        options.inter_op_num_threads=1
        options.add_session_config_entry('session.intra_op.allow_spinning','0')
        cuda_options=dict(gpu_mem_limit=2*1024*1024*1024,arena_extend_strategy='kSameAsRequested',
                          cudnn_conv_use_max_workspace='0')
        self.engine['cuda_provider_options']=cuda_options if device=='cuda' else None
        providers=[('CUDAExecutionProvider',cuda_options),'CPUExecutionProvider'] if device=='cuda' else ['CPUExecutionProvider']
        for model in [self.detector,*self.recognizers]:
            model.session=ort.InferenceSession(model.model_path,options,providers=providers)
        if device=='cuda' and any('CUDAExecutionProvider' not in m.session.get_providers()
                                 for m in [self.detector,*self.recognizers]):
            raise RuntimeError('Requested CUDA OCR is unavailable')
        # Share one model set between image jobs. The detector mutates its
        # image dimensions, so its entire detect call must be serialized.
        detect=self.detector.detect
        detector_gate=threading.Lock()
        def bounded_detect(img):
            with detector_gate:
                return detect(img)
        self.detector.detect=bounded_detect
        for model in self.recognizers:
            def bounded_read(img,read=model.read,gate=threading.Semaphore(1)):
                with gate:
                    return read(img)
            model.read=bounded_read

    def read(self, img, name):
        import numpy as np
        if self.ocr is None:
            import io
            pixels=io.BytesIO();img.convert('RGB').save(pixels,format='PNG')
            lines=self.lines(pixels.getvalue(),img.size,self.config)
            text='\n'.join(line['text'] for line in [*lines,*self.geometry_diagnostics])
            for line in lines:
                x,y,a,b=line['box'];line['boundingBox']=[[x,y],[a,y],[a,b],[x,b]]
            return dict(kind='raw_text_page',status='ocr_text' if text else 'ocr_no_text_detected',text=text,lines=lines,
                engine=self.pin,image_width=img.width,image_height=img.height,native_layout=self.native_layout,geometry_diagnostics=self.geometry_diagnostics)
        if img.width*img.height>20_000_000:
            parts=[];lines=[]
            for top in range(0,img.height,1984):
                for left in range(0,img.width,1984):
                    box=[left,top,min(left+2048,img.width),min(top+2048,img.height)]
                    with img.crop(box) as tile:part=self.read(tile,name+f'-{left}-{top}')
                    parts.append(dict(bbox=box,text=part['text'],status=part['status']))
                    lines.extend(dict(line,tile_bbox=box) for line in part['lines'])
            text='\n'.join(p['text'] for p in parts if p['text'].strip())
            return dict(kind='raw_text_page',status='ocr_text' if text else 'ocr_no_text_detected',text=text,
                lines=lines,tiles=parts,engine=self.engine,image_width=img.width,image_height=img.height,
                geometry='Line coordinates are tile-local; tile_bbox locates each tile in original pixels; 64-pixel overlap retained')
        try:
            result = self.ocr._run_ocr_on_image_array(self.detector,*self.recognizers,
                name,np.asarray(img.convert('RGB')),'',False)
        except Exception as error:
            message=str(error).lower()
            if any(marker in message for marker in ('failed to allocate memory','available memory of',
                    'out of memory','cuda error','cuda failure','cudnn failure')):
                from concurrent.futures import BrokenExecutor
                raise BrokenExecutor('Local OCR runtime failed; stop and repair before retry: '+str(error)) from error
            raise
        text = result['text'].replace('\x00','\\u0000')
        return dict(kind='raw_text_page',status='ocr_text' if text.strip() else 'ocr_no_text_detected',
            text=text,lines=result['json_lines'],engine=self.engine,
            image_width=result['img_width'],image_height=result['img_height'],
            native_layout=decode_layout(result['page_xml']))


    def lines(self, pixels, dimensions, config):
        if self.ocr is not None:
            import io
            from PIL import Image
            with Image.open(io.BytesIO(pixels)) as image:
                page = self.read(image, "page")
            self.geometry_diagnostics=[]
            self.native_layout=page.get("native_layout", {"blocks":[],"lines":{},"state":"not_available"})
            lines=decode_lines({"contents":[page["lines"]]}, dimensions, diagnostics=self.geometry_diagnostics)
            for line in lines:line.update(self.native_layout.get("lines",{}).get(str(line.get("native_id")),{}))
            return lines
        timeout = config.get('timeout', 120)
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 600:
            raise ValueError('NDLOCR timeout must be 1..600 seconds')
        with tempfile.TemporaryDirectory(prefix='kanji-ndlocr-') as folder:
            root = Path(folder); source = root / 'page.png'; source.write_bytes(pixels)
            (root / 'output').mkdir()  # Upstream returns success without OCR when absent.
            try:
                subprocess.run([*self.command, '--sourceimg', str(source),
                                '--output', str(root / 'output'), '--device', 'cpu'],
                               check=True, capture_output=True, timeout=timeout,cwd=self.cwd)
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
            tile=line.get('tile_bbox')
            if tile:
                if len(tile)!=4 or not all(type(v) is int for v in tile) or not (0<=tile[0]<tile[2]<=width and 0<=tile[1]<tile[3]<=height):raise ValueError('Invalid NDLOCR tile')
                if not all(0<=x<=tile[2]-tile[0] and 0<=y<=tile[3]-tile[1] for x,y in points):raise ValueError('Line outside NDLOCR tile')
                points=[[x+tile[0],y+tile[1]] for x,y in points]
            box = [math.floor(min(p[0] for p in points)), math.floor(min(p[1] for p in points)),
                   math.ceil(max(p[0] for p in points)), math.ceil(max(p[1] for p in points))]
            if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                if diagnostics is None:raise ValueError('NDLOCR box is outside the image')
                diagnostics.append({'text':text,'original_geometry':points,'state':'unresolved',
                                    'reason':'ndlocr_box_outside_image','geometry':None,
                                    'coverage_eligible':False,'crop_created':False})
                continue
            lines.append({'box': box, 'text': text,'native_id':line.get('id',native_order),
                          'native_order':native_order,'native_group':group_index,'tile_bbox':tile,
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


def honkoku_layers(markup):
    """Separate annotations from body without deleting unknown-glyph evidence."""
    value=markup.replace('<UNK>','□').replace('<MASK>','□')
    pattern=r'<(rt2?|KAERI|OKURI)>(.*?)</\1>'
    annotations=[dict(kind=m.group(1),text=m.group(2)) for m in re.finditer(pattern,value,re.S)]
    body=re.sub(pattern,'',value,flags=re.S)
    body=re.sub(r'</?(?:ruby|WARI)>|<(?:TATE|WARI_SEP|BLOCK)>','',body)
    return dict(body=body,annotations=annotations,malformed_annotation=bool(re.search(r'</?(?:rt2?|KAERI|OKURI)>',body)))


class LineComparison:
    """Isolated local comparison; upstream preprocessing, immutable model pins, no L1 selection."""
    def __init__(self, honkoku, koten, ndl):
        import hashlib, importlib.util
        import numpy as np
        import onnxruntime as ort
        import yaml
        self.np=np; self.paths={}; self.sessions={}; self.models={}
        options=ort.SessionOptions(); options.intra_op_num_threads=1; options.inter_op_num_threads=1
        options.add_session_config_entry('session.intra_op.allow_spinning','0')
        def session(path):
            self.paths[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
            return ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider'])
        for name in ('encoder','decoder_prefill','decoder_step'):
            self.sessions[name]=session(honkoku/'onnx'/f'{name}.int8.onnx')
        tk=json.loads((honkoku/'tokenizer.json').read_text()); vocab=dict(tk['model']['vocab'])
        vocab.update({t['content']:t['id'] for t in tk.get('added_tokens',[])})
        self.inv={v:k for k,v in vocab.items()}
        self.paths[str(honkoku/'tokenizer.json')]=hashlib.sha256((honkoku/'tokenizer.json').read_bytes()).hexdigest()
        for name,folder,pattern in [('koten',koten,'parseq-ndl-32x384-tiny-10.onnx'),
                                    ('ndl_print_100',ndl,'*100-tiny*.onnx')]:
            source=folder/'parseq.py'; spec=importlib.util.spec_from_file_location('comparison_'+name,source)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            models=list((folder/'model').glob(pattern))
            if len(models)!=1:raise ValueError('Expected exactly one recognition model: '+name)
            model=module.PARSEQ.__new__(module.PARSEQ); model.session=session(models[0])
            charset=folder/'config/NDLmoji.yaml'
            model.charlist=list(yaml.safe_load(charset.read_text())['model']['charset_train'])
            model.input_names=[i.name for i in model.session.get_inputs()]
            model.output_names=[i.name for i in model.session.get_outputs()]
            model.input_height,model.input_width=model.session.get_inputs()[0].shape[2:]
            self.models[name]=model
            for p in (source,charset):self.paths[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        self.producer=dict(name='identical-native-crop-reader-comparison',version='1',files=self.paths,
                           onnxruntime=ort.__version__,device='CPU',threads=1,decode='greedy; Honkoku maximum 192 tokens',
                           implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

    def read(self, image):
        from PIL import Image
        np=self.np; array=np.array(image)
        texts={name:model.read(array) for name,model in self.models.items()}
        # Exact upstream Honkoku ONNX image preparation and cached greedy decoding.
        rotated=image.rotate(-90,expand=True) if image.height>image.width else image
        width=max(1,min(2048,round(rotated.width*256/rotated.height)))
        resized=rotated.resize((width,256),Image.Resampling.BICUBIC)
        padded=Image.new('RGB',(2048,256),'white');padded.paste(resized,(0,0))
        tensor=((np.asarray(padded,np.float32)/255-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)).transpose(2,0,1)[None]
        enc,pre,step=(self.sessions[k] for k in ('encoder','decoder_prefill','decoder_step'))
        h=enc.run(None,{enc.get_inputs()[0].name:tensor})[0]
        out=pre.run(None,{'input_ids':np.array([[2]],np.int64),'encoder_hidden_states':h})
        ids=[int(out[0][0,-1].argmax())]
        past_names=[i.name for i in step.get_inputs() if i.name.startswith('past_')]
        for _ in range(191):
            if ids[-1]==3:break
            out=step.run(None,{'input_ids':np.array([[ids[-1]]],np.int64),'encoder_hidden_states':h,
                              **dict(zip(past_names,out[1:]))})
            ids.append(int(out[0][0,-1].argmax()))
        markup=''.join(self.inv.get(i,'') for i in ids if i not in (0,2,3))
        texts['honkoku']=re.sub(r'<[^>]+>','',markup)
        return dict(texts=texts,honkoku_markup=markup,honkoku_ended=ids[-1]==3)

"""Bounded native-pixel layout/crops; derived data only, no source-owner writes."""
from pathlib import Path
from .request_contracts import digest,canonical
LAYOUT_VERSION='ndl-page-blocks-v5-header-retry'

def regions_from_image(raw,request,*,pdf=False):
    import cv2,numpy as np
    config=request.get('image_config',{})
    backend=request.get('ocr_config',{}).get('backend','ndl')
    if backend!='ndl':raise ValueError('Only the current NDLOCR backend is supported')
    if pdf:
        import pymupdf
        with pymupdf.open(stream=raw,filetype='pdf') as doc:
            number=request.get('page',0)
            if not isinstance(number,int) or not 0<=number<len(doc):raise ValueError('Invalid PDF page')
            dpi=config.get('dpi',150)
            if not isinstance(dpi,(int,float)) or not 72<=dpi<=300:raise ValueError('dpi must be 72..300')
            page=doc[number]
            if page.rect.width*page.rect.height*(dpi/72)**2>40_000_000:raise ValueError('Rendered page exceeds 40M pixels')
            page_dimensions=[float(page.rect.width),float(page.rect.height)]
            pix=page.get_pixmap(dpi=int(dpi),alpha=False)
            image=cv2.imdecode(np.frombuffer(pix.tobytes('png'),dtype=np.uint8),cv2.IMREAD_COLOR)
    else:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(raw)) as probe:
            frame=request.get('page',0)
            if not isinstance(frame,int) or not 0<=frame<getattr(probe,'n_frames',1):raise ValueError('Invalid image frame')
            probe.seek(frame)
            if probe.width*probe.height>40_000_000:raise ValueError('Image exceeds 40M pixels')
            image=cv2.cvtColor(np.array(probe.convert('RGB')),cv2.COLOR_RGB2BGR)
    if image is None:raise ValueError('Cannot decode source image')
    h,w=image.shape[:2]
    transforms={'source_to_pixels':[w/page_dimensions[0],h/page_dimensions[1]] if pdf else [1,1],'native_masks':[]}
    # Mask only usable native text rectangles; scanned/vector ink elsewhere must
    # remain visible to the same contour/OCR owner.
    for block in request.get('native_pdf_blocks',[]):
        for x0,y0,x1,y1 in block.get('coverage_masks',[block['geometry']]):
            sx,sy=transforms['source_to_pixels']
            box=[max(0,int(x0*sx)),max(0,int(y0*sy)),min(w,int(x1*sx+1)),min(h,int(y1*sy+1))]
            image[box[1]:box[3],box[0]:box[2]]=255
            transforms['native_masks'].append(box)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    ink=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    # Remove full-page frames and tiny isolated noise before line grouping.
    n,labels,stats,_=cv2.connectedComponentsWithStats(ink,8)
    clean=np.zeros_like(ink);heights=[];widths=[]
    for x,y,bw,bh,area in stats[1:]:
        if area>=3 and bw<w*.8 and bh<h*.8:
            heights.append(int(bh));widths.append(int(bw))
    orientation=config.get('orientation','auto')
    if orientation not in ('auto','horizontal','vertical'):raise ValueError('Invalid image orientation')
    # Long native glyph runs are an explicit, reproducible hint; ambiguous pages
    # default horizontal. A supplied publisher orientation takes precedence.
    if orientation=='auto':
        tall=sum(bh>bw*3 and bh>h*.08 for x,y,bw,bh,a in stats[1:])
        wide=sum(bw>bh*3 and bw>w*.08 for x,y,bw,bh,a in stats[1:])
        orientation='vertical' if tall>wide and tall>=3 else 'horizontal'
    keep=np.zeros(n,dtype=np.uint8)
    for label,(x,y,bw,bh,area) in enumerate(stats[1:],1):
        if area>=3 and bw<w*.8 and bh<h*.8:keep[label]=255
    clean=keep[labels]
    median=float(np.median(widths if orientation=='vertical' else heights)) if heights else 8
    gap=max(3,min(80,int(median*.65)))
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(3,gap) if orientation=='vertical' else (gap,3))
    joined=cv2.dilate(clean,kernel)
    contours,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    for contour in contours:
        x,y,bw,bh=cv2.boundingRect(contour)
        if bw*bh<max(24,median*median*.5) or cv2.countNonZero(clean[y:y+bh,x:x+bw])<8:continue
        boxes.append([max(0,x-2),max(0,y-2),min(w,x+bw+2),min(h,y+bh+2)])
    boxes.sort(key=(lambda b:(-b[0],b[1])) if orientation=='vertical' else (lambda b:(b[1],b[0])))
    # One local page pass discovers text lines/columns and recognizes them. Crop
    # OCR remains the fallback/retry path; page TSV is cached with exact runtime.
    unlocated=[];native_layout={'blocks':[], 'lines':{}, 'state':'not_run'};lines=[]
    page_predictions=[];page_metrics={'ocr_calls':0,'ocr_cache_hits':0}
    raw_page_lines=[];header_retries=[]
    page_pin=None;coverage_disposition={'method':'deterministic_contours','excluded':'area<3 or full-page frames; nonmaterial contour thresholds'}
    page_enabled=cv2.countNonZero(clean) and request.get('local_ocr',True) and config.get('page_ocr',True)
    if page_enabled and backend=='ndl':
        from .readers.ocr.ndlocr_lite import NDLOCR
        from .result_cache import read_cache,write_cache,DEPENDENCIES
        engine=NDLOCR(request.get('ocr_config',{}));page_pin=engine.pin
        dep={k:None for k in DEPENDENCIES}
        dep.update(source_sha256=digest(raw),crop_sha256=digest(raw),locator='page:'+str(request.get('page',0)),adapter_version=page_pin,ocr_config=request.get('ocr_config',{}),stage='page_ocr',image_config=config,layout_version=LAYOUT_VERSION,coordinate_transform=transforms)
        root=Path(request['cache_dir'])
        cached=read_cache(root,dep)
        if cached is None:
            page_metrics['ocr_calls']=1
            lines=engine.lines(cv2.imencode('.png',image)[1].tobytes(),[w,h],request.get('ocr_config',{}))
            unlocated=getattr(engine,'geometry_diagnostics',[])
            native_layout=getattr(engine,'native_layout',native_layout)
            write_cache(root,dep,{'lines':lines,'geometry_diagnostics':unlocated,'native_layout':native_layout})
        else:
            page_metrics['ocr_cache_hits']=1;lines=cached['lines'];unlocated=cached.get('geometry_diagnostics',[]);native_layout=cached.get('native_layout',native_layout)
        raw_page_lines=[dict(line) for line in lines]
        # Retry only detector-owned headers omitted by the page recognizer.
        # These are literal OCR proposals on bounded pixels, never semantic corrections.
        def overlap_area(a,b):
            return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
        for block in native_layout.get('blocks',[]):
            if block['type']!='running_header' or not block.get('geometry'):continue
            a,b,c,d=block['geometry'];box=[max(0,int(a)),max(0,int(b)),min(w,int(c+1)),min(h,int(d+1))]
            a,b,c,d=box
            if c<=a or d<=b:continue
            if any(line.get('text','').strip() and overlap_area(box,line['box'])/max(1,(c-a)*(d-b))>=.7 for line in lines):continue
            crop=cv2.imencode('.png',image[b:d,a:c])[1].tobytes()
            header_dep={**dep,'stage':'native_header_crop_retry_v1','crop_sha256':digest(crop),'locator':block['id']}
            retry=read_cache(root,header_dep)
            if retry is None:
                attempts=[]
                for border in (0,24):
                    pixels=image[b:d,a:c]
                    if border:pixels=cv2.copyMakeBorder(pixels,border,border,border,border,cv2.BORDER_CONSTANT,value=(255,255,255))
                    encoded=cv2.imencode('.png',pixels)[1].tobytes()
                    try:
                        page_metrics['ocr_calls']+=1
                        proposal=engine(encoded,{},request.get('ocr_config',{}))
                    except (RuntimeError,OSError,ValueError) as error:
                        proposal={'text':'','state':'unresolved','error':type(error).__name__}
                    attempts.append({'input_sha256':digest(encoded),'border_pixels':border,'proposal':proposal})
                    if len(proposal.get('text','').strip())>=2:break
                retry={'text':attempts[-1]['proposal'].get('text',''),'attempts':attempts,'state':'literal_OCR_proposal'}
                write_cache(root,header_dep,retry)
            else:page_metrics['ocr_cache_hits']+=1
            header_retries.append({'native_block':block['id'],'geometry':box,'crop_sha256':digest(crop),**retry})
            if retry['text'].strip():
                lines.append({'box':box,'text':retry['text'],'role':'running_header','orientation':'vertical',
                              'native_block':block['id'],'native_order':len(lines),'origin':'bounded_header_crop_retry'})
        # Keep NDL reading order and retain other material ink as unresolved.
        boxes=[line['box'] for line in lines]
        page_predictions=[engine.prediction(line['text']) for line in lines]
        covered=np.zeros_like(clean)
        for x0,y0,x1,y1 in boxes:covered[y0:y1,x0:x1]=255
        # Native illustration blocks remain explicit figures rather than hundreds
        # of spurious OCR snippets from their strokes.
        for block in native_layout.get('blocks',[]):
            if block.get('type')=='figure' and block.get('geometry'):
                a,b,c,d=[int(v) for v in block['geometry']]
                covered[max(0,b):min(h,d),max(0,a):min(w,c)]=255
        unexplained=cv2.bitwise_and(clean,cv2.bitwise_not(covered))
        context_kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(3,max(gap,int(median*2))) if orientation=='vertical' else (max(gap,int(median*2)),3))
        missing,_=cv2.findContours(cv2.dilate(unexplained,context_kernel),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in missing:
            x0,y0,bw,bh=cv2.boundingRect(contour);x1=min(w,x0+bw);y1=min(h,y0+bh);box=[x0,y0,x1,y1]
            if cv2.countNonZero(unexplained[y0:y1,x0:x1])>=8:
                boxes.append(box);page_predictions.append({**engine.prediction(''),'reason':'material_ink_without_page_ocr'})
                covered[y0:y1,x0:x1]=255
        coverage_disposition={'method':'ndl_lines_plus_unexplained_contours','material_ink_pixels':cv2.countNonZero(clean),'covered_material_ink_pixels':cv2.countNonZero(cv2.bitwise_and(clean,covered)),'excluded':'area<3 or full-page frame components; residual groups<8 ink pixels'}
    limit=config.get('max_regions',512)
    if not isinstance(limit,int) or not 1<=limit<=2048:raise ValueError('max_regions must be 1..2048')
    if len(boxes)>limit:raise ValueError('Detected regions exceed bound; refine layout configuration')
    cache=Path(request.get('cache_dir',Path(__file__).resolve().parent/'cache'))
    source_sha=digest(raw);layout_sha=digest(canonical({'version':LAYOUT_VERSION,'opencv':cv2.__version__,'config':config,'engine':page_pin,'pdf':pdf,'page':request.get('page',0),'coordinate_transform':transforms}))
    unlocated=[{**item,'region_id':f"page:{request.get('page',0)}:unlocated:{i}",
                'identity':{'source_sha256':source_sha,'layout_sha256':layout_sha,'page':request.get('page',0),
                            'source_dimensions':[w,h],'coordinate_space':'rendered_pixels' if pdf else 'native_pixels'}}
               for i,item in enumerate(unlocated)]
    result=[]
    for i,box in enumerate(boxes):
        x0,y0,x1,y1=box
        data=cv2.imencode('.png',image[y0:y1,x0:x1])[1].tobytes();crop_sha=digest(data)
        target=cache/'crops'/crop_sha[:2]/(crop_sha+'.png')
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes(data)
        elif digest(target.read_bytes())!=crop_sha:raise ValueError('Corrupt crop cache')
        rid=f"page:{request.get('page',0)}:line:{i}"
        line=lines[i] if i<len(lines) else {}
        result.append({'region_id':rid,'text':page_predictions[i]['text'] if page_predictions else '','page_ocr':page_predictions[i] if page_predictions else None,'crop':str(target),'geometry':box,'orientation':line.get('orientation',orientation),'native_block':line.get('native_block'),'native_order':line.get('native_order',i),'role':line.get('role','unresolved_ink' if not line else 'text_line'),'style':config.get('style','unknown'),'origin':'raw_image','identity':{'source_sha256':source_sha,'crop_sha256':crop_sha,'layout_sha256':layout_sha,'page':request.get('page',0),'source_dimensions':[w,h],'coordinate_space':'rendered_pixels' if pdf else 'native_pixels'}})
    return result,{'route':'rendered_pdf' if pdf else 'raw_image','layout_version':LAYOUT_VERSION,'layout_sha256':layout_sha,'dimensions':[w,h],'coordinate_transform':transforms,'orientation':orientation,'native_layout':native_layout,'regions_detected':len(result),'unlocated_ocr_regions':unlocated,'unlocated_ocr_region_count':len(unlocated),'region_inventory_state':'requires_review' if unlocated else 'within_region_bound','blank':not bool(cv2.countNonZero(clean)),'accuracy_qualified':False,'page_ocr_metrics':page_metrics,'engine_pin':page_pin,'coverage_disposition':coverage_disposition,'original_page_OCR_lines':raw_page_lines,'header_crop_retries':header_retries}


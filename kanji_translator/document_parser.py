"""Native -> exact reviewed transcript -> failed-region OCR -> proposal queue."""
import copy,json,re,time
from pathlib import Path
from .request_contracts import SCHEMA,digest,require_hash,validate_request
from .text_normalization import forms,forms_with_offsets,RULE_SHA
from .source_evidence import reviewed_reuse,retained_json
from .candidate_lookup import candidates
from .result_cache import read_cache,write_cache,DEPENDENCIES

def read_retained(request):
    if request.get('adapter'):
        import importlib
        module, function = request['adapter'].split(':',1)
        return getattr(importlib.import_module(module),function)(request)
    if request.get('owner') or 'route' in request:
        raise ValueError('Private retained owners require an explicit adapter module:function')
    return retained_json(request)

def _native(request):
    kind=request.get('kind','text');raw=None
    if kind=='library_ocr':
        from .readers.ocr.retained import read
        regions,payload=read(request)
        request['sha256']=payload['source']['sha256']
        request['identity']={**request.get('identity',{}),'source_sha256':request['sha256']}
        return regions,payload
    if kind=='retained_layout':
        from .document_layout import layout_regions
        page=read_retained(request['retained'])
        if isinstance(page.get('payload'),dict):page={**page['payload'],'source':page.get('source',page['payload'].get('source',{})),'id':page.get('pid','unknown')+':'+str(page.get('koma','unknown'))}
        request['_retained_layout']=page
        source=page.get('source') or {}
        source_sha=source.get('sha256') or source.get('raw_sha256') or page.get('source_sha256')
        if not source_sha:raise ValueError('Retained layout lacks source identity')
        request['sha256']=require_hash(source_sha,'retained source sha256')
        return layout_regions(page),{'origin':'retained_source_layout','source':page.get('source'),'profile':page.get('profile')}

    if 'path' in request:
        raw=Path(request['path']).read_bytes()
        if digest(raw)!=require_hash(request['sha256']):raise ValueError('Source hash mismatch')
    if kind=='retained':
        payload=read_retained(request)
        if isinstance(payload,str):return [{'region_id':'retained','text':payload,'origin':'retained_unreviewed'}],payload
        source=payload.get('source') or {}
        source_sha=source.get('sha256') or source.get('raw_sha256') or payload.get('source_sha256')
        if source_sha:request['sha256']=require_hash(source_sha,'retained source sha256')
        body=payload.get('payload',payload)
        blocks=body.get('blocks') or body.get('paragraphs') or body.get('regions')
        if blocks is None:blocks=[{'text':body.get('literal_text',body.get('text',''))}]
        result=[]
        for i,b in enumerate(blocks):
            choices=b.get('candidates',[])
            text=b.get('text',b.get('literal_text',choices[0].get('text','') if choices else ''))
            result.append({**b,'region_id':b.get('region_id',b.get('paragraph_id',str(i))),'text':text,'origin':'retained_unreviewed','identity':{'source_sha256':request.get('sha256') or request.get('document_sha256') or digest(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()),**b.get('identity',{})}})
        return result,payload
    if kind=='image':
        if raw is None:raise ValueError('Image needs hash-bound path')
        from .image_regions import regions_from_image
        return regions_from_image(raw,request)
    if kind=='pdf':
        import pymupdf
        if raw is None:raise ValueError('PDF needs hash-bound path')
        with pymupdf.open(stream=raw,filetype='pdf') as doc:
            number=request.get('page',0)
            if not isinstance(number,int) or number<0 or number>=len(doc):raise ValueError('Invalid PDF page')
            page=doc[number]
            blocks=[]
            for i,block in enumerate(page.get_text('rawdict')['blocks']):
                if block.get('type')!=0:continue
                lines=block.get('lines',[])
                text=''.join(''.join(c['c'] for span in line['spans'] for c in span['chars'])+'\n' for line in lines)
                masks=[list(c['bbox']) for line in lines for span in line['spans'] for c in span['chars'] if c['c'].strip()]
                blocks.append({'region_id':f'page:{number}:block:{i}','text':text,'geometry':list(block['bbox']),'coverage_masks':masks,'origin':'native_pdf'})
        from .image_regions import regions_from_image
        usable=[b for b in blocks if _usable(b['text'])]
        raster,payload=regions_from_image(raw,{**request,'native_pdf_blocks':usable},pdf=True)
        payload['native_blocks']=len(usable)
        payload['coverage_policy']='native glyph rectangles masked before unresolved ink detection'
        return usable+raster,payload
    if kind=='regions':
        if not isinstance(request.get('regions'),list):raise ValueError('regions list required')
        return request['regions'],None
    text=request.get('text')
    if raw is not None:
        text=raw.decode(request.get('encoding','utf-8'),errors='strict')
    if not isinstance(text,str):raise ValueError('Text or hash-bound path is required')
    if kind in ('html','club_record','club_smith','club_catalogue'):
        if kind.startswith('club_'):
            from .readers.html.nihonto_club import parse_record_html,parse_smith_html,parse_catalogue_html
            parser={'club_record':parse_record_html,'club_smith':parse_smith_html,'club_catalogue':parse_catalogue_html}[kind]
            payload=parser(text,request.get('source_url',''))
        else:payload=None
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(text,'html.parser')
        for node in soup(['script','style','noscript']):node.decompose()
        literal=soup.get_text(' ',strip=True)
        return [{'region_id':'dom','text':literal,'origin':'native_html'}],payload
    if kind not in ('text','field','regions'):raise ValueError('Unsupported input kind: '+kind)
    return request.get('regions') if kind=='regions' else [{'region_id':'field' if kind=='field' else 'text','text':text,'origin':'native_unicode'}],None

def _usable(text):
    # Mechanical validity, not accuracy probability. Replacement/unknown glyphs
    # escalate only their region; rare and out-of-lexicon CJK remain literal.
    return bool(text.strip()) and not re.search(r'\[unreadable\]|[\ufffd□〓]',text)

def parse(request, *, ocr_adapter=None, vision_adapter=None):
    """Preserve native characters, then interpret source-supported complete spans."""
    request=dict(request)
    validate_request(request)
    if vision_adapter is not None:
        raise ValueError('Generic vision rewriting is retired; retain separate source-reviewed character evidence')
    if request.get('kind') in ('image','pdf'):
        from .data_paths import cache_dir, external
        request.setdefault('cache_dir',str(external(cache_dir())))
    regions,payload=_native(request)
    from .document_layout import document_groups, mark_duplicate_lines
    for index,region in enumerate(regions):region.setdefault('region_id',str(index))
    mark_duplicate_lines(regions)
    groups=document_groups(request,regions,payload)
    from .entry_structure import tabs
    index_evidence=[{**name,'region_id':r['region_id'],'geometry':r.get('geometry')}
                    for r in regions for name in tabs(r.get('text',''))]
    metrics={key:0 for stage in ('ocr','vision','lexical','reading','translation') for key in (stage+'_calls',stage+'_cache_hits')}
    if isinstance(payload,dict):metrics.update(payload.get('page_ocr_metrics',{}))
    out=[];enriched=[];unresolved=[];mentions=[]
    from .region_enrichment import lookup_lexical
    from .semantic_groups import interpret
    for region in regions:
        literal=region.get('text') or '';reading=literal;rid=region['region_id']
        identity={**request.get('identity',{}),**region.get('identity',{})}
        identity.setdefault('source_sha256',request.get('sha256') or digest((request.get('text') or '').encode()))
        for key,default in [('locator',rid),('geometry',region.get('geometry')),('orientation',region.get('orientation','unknown')),('style',region.get('style','unknown')),('field_type',request.get('field_type','unknown'))]:identity.setdefault(key,default)
        ocr=region.get('page_ocr');state='proposal' if ocr else 'literal';review=None
        context={**request.get('context',{}),**region.get('context',{}),**groups['region_context'].get(rid,{})}
        context.update(entry_index_names=sorted({r['literal'] for r in index_evidence}),entry_index_evidence=index_evidence)
        from .reviewed_readings import lookup_review
        spec=region.get('review') or request.get('reviews',{}).get(rid) or lookup_review(identity)
        if spec:
            review=reviewed_reuse(spec,identity)
            if review['reusable']:reading=review['record']['literal_text'];state='source_verified'
        if not _usable(reading) and not ocr and state!='source_verified' and region.get('crop') and request.get('local_ocr',True):
            crop=Path(region['crop']).read_bytes()
            if digest(crop)!=require_hash(identity.get('crop_sha256'),'crop_sha256'):raise ValueError('OCR crop hash mismatch')
            engine=ocr_adapter;pin=request.get('adapter_version')
            if engine is None:
                from .readers.ocr import local_engine
                engine=local_engine(request.get('ocr_config',{}));pin=engine.pin
            if not pin:raise ValueError('OCR adapter version required')
            dep={**{key:None for key in DEPENDENCIES},**identity,'stage':'literal_crop_ocr','adapter_version':pin,'ocr_config':request.get('ocr_config',{})}
            ocr=read_cache(request['cache_dir'],dep) if request.get('cache_dir') else None
            if ocr is None:
                ocr=engine(crop,region,request.get('ocr_config',{}));metrics['ocr_calls']+=1
                if not isinstance(ocr,dict):ocr={'text':str(ocr or '')}
                if request.get('cache_dir'):write_cache(request['cache_dir'],dep,ocr)
            else:metrics['ocr_cache_hits']+=1
            reading=ocr.get('text','');state='proposal'
        lexical=lookup_lexical(reading,identity,context,request,metrics)
        semantic=interpret(reading,lexical,context,request.get('semantic_config'))
        if context.get('semantic_exclusion'):
            semantic['mentions']=[]
            semantic['interpretation']['claims']=[]
            semantic['interpretation']['clauses']=[]
            semantic['exclusion']=context['semantic_exclusion']
        bad=not _usable(reading) or bool(ocr and (ocr.get('unresolved') or ocr.get('output_truncated')))
        if bad and state!='source_verified':state='unresolved';unresolved.append(rid)
        row={'region_id':rid,**forms(literal),'reading_text':reading,'state':state,
             'origin':region.get('origin','native_region'),'identity':identity,'context':context,
             'review':review,'lexical':lexical,'ocr':ocr,'mechanical':[candidates({**request,'pattern':reading,'context':context})] if re.search('[□〓�]',reading) else [],'identity_accepted':False}
        out.append(row)
        for mention in semantic['mentions']:
            mention.update(region_id=rid,source_sha256=identity['source_sha256'],
                           geometry=identity.get('geometry'),geometry_scope='whole native OCR line; no invented character boxes')
            mention['mention_id']=digest(json.dumps([identity['source_sha256'],request.get('page',0),rid,mention['start'],mention['end'],mention['literal']],ensure_ascii=False).encode())
            mentions.append(mention)
        search,offsets=forms_with_offsets(reading)
        enriched.append({'region_id':rid,'original_text':literal,'raw_ndl_text':literal,
                         'literal_text':reading,'enhanced_text':reading,'search_form':search,
                         'search_offsets':offsets,'identity':identity,'context':context,'lexical':lexical,
                         'semantic':semantic,'review_state':state,'abstained':state=='unresolved',
                         'readings':None,'translations':[],'english':None,'output_truncated':bool(ocr and ocr.get('output_truncated'))})
    # Continue only inside an explicit native coherent text block. Each joined
    # codepoint remains aligned to the native region and its original offsets.
    by_region={row['region_id']:row for row in out}
    enrichment_by_region={row['region_id']:row for row in enriched}
    block_semantics=[]
    for block in groups.get('reading_blocks',[]):
        ids=block['region_ids']
        if len(ids)<2 or block['orientation'] not in ('vertical','horizontal'):continue
        joined='';alignment=[]
        for rid in ids:
            value=by_region[rid]['reading_text'];start=len(joined);joined+=value
            alignment.append({'region_id':rid,'block_start':start,'block_end':len(joined),'region_start':0,'region_end':len(value),'geometry':by_region[rid]['identity'].get('geometry')})
        context={**by_region[ids[0]]['context'],'group_id':block['block_id']}
        lexical=lookup_lexical(joined,{'block_id':block['block_id'],'source_sha256':by_region[ids[0]]['identity']['source_sha256']},context,request,metrics)
        semantic=interpret(joined,lexical,context,request.get('semantic_config'))
        mentions=[m for m in mentions if m['region_id'] not in ids]
        for mention in semantic['mentions']:
            segments=[]
            for segment in alignment:
                start=max(mention['start'],segment['block_start']);end=min(mention['end'],segment['block_end'])
                if start<end:
                    local_start=start-segment['block_start'];local_end=end-segment['block_start']
                    segments.append({'region_id':segment['region_id'],'start':local_start,'end':local_end,
                                     'literal':by_region[segment['region_id']]['reading_text'][local_start:local_end],
                                     'geometry':segment['geometry']})
            sha=by_region[ids[0]]['identity']['source_sha256']
            boxes=[segment['geometry'] for segment in segments if segment['geometry']]
            geometry=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else None
            mention.update(region_id=segments[0]['region_id'],region_ids=[seg['region_id'] for seg in segments],
                           source_segments=segments,source_sha256=sha,geometry=geometry,
                           geometry_scope='union of aligned whole native OCR lines',block_id=block['block_id'])
            mention['mention_id']=digest(json.dumps([sha,request.get('page',0),block['block_id'],mention['start'],mention['end'],mention['literal']],ensure_ascii=False).encode())
            mentions.append(mention)
        for rid in ids:
            enrichment_by_region[rid]['semantic']['mentions']=[m for m in semantic['mentions'] if rid in m['region_ids']]
            enrichment_by_region[rid]['semantic']['selection_owner']=block['block_id']
        block_semantics.append({'block':block,'literal_text':joined,'literal_alignment':alignment,
                                'text_kind':'ordered_derivative_with_native_offsets','lexical':lexical,'semantic':semantic})
    blocked={rid for block in block_semantics for rid in block['block']['region_ids']}
    interpretations=[{'unit_id':r['region_id'],'source_sha256':r['identity']['source_sha256'],
                      'geometry':r['identity'].get('geometry'),'literal_text':r['literal_text'],
                      'entry_structure':r['semantic']['entry_structure'],**r['semantic']['interpretation']}
                     for r in enriched if r['region_id'] not in blocked]
    interpretations.extend({'unit_id':b['block']['block_id'],'literal_text':b['literal_text'],
                            'source_sha256':by_region[b['block']['region_ids'][0]]['identity']['source_sha256'],
                            'literal_alignment':b['literal_alignment'],
                            'entry_structure':b['semantic']['entry_structure'],**b['semantic']['interpretation']}
                           for b in block_semantics)
    from .document_layout import unique_mentions
    mentions=unique_mentions(mentions)
    return {'schema':SCHEMA,'raw_ndl_transcript':payload['raw_transcript'] if request.get('kind')=='library_ocr' else '\n'.join(r['raw_text'] for r in out),
            'enhanced_transcript':'\n'.join(r['literal_text'] for r in enriched),
            'document_groups':groups,'regions':out,'enrichment':{'schema':'kanji-enrichment-v2','regions':enriched,'automatic_promotion':False},
            'semantic_mentions':mentions,'semantic_blocks':block_semantics,'japanese_interpretations':interpretations,'native_payload':payload,'metrics':metrics,
            'enhancement':{'profile':'retired','changes':[]},'vision_proposals':[],
            'unresolved_regions':len(unresolved),'vision_deferred':0,'probability_correct':None}

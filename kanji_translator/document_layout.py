"""Source-owned document groups and associations, before lexical enrichment.

Only explicit layout/metadata establishes hierarchy or links. Missing chapter,
caption/body references and cross-page continuity stay unknown. Proximity is
never promoted to a document relationship.
"""
from .request_contracts import canonical,digest
VERSION='source-document-groups-v3-native-blocks'


def unique_mentions(mentions):
 """Retain repeated native witnesses, count one geometrically duplicated span.

 This only deduplicates the same complete literal/category in different native
 lines with strongly overlapping enclosures. Repetitions within a line survive.
 """
 def area(m):
  b=m.get('geometry');return (b[2]-b[0])*(b[3]-b[1]) if b else float('inf')
 from collections import Counter
 occurrences=Counter((m['region_id'],m['literal'],m['selection']['category']) for m in mentions)
 selected=[]
 for row in sorted(mentions,key=area):
  a=row.get('geometry');duplicate=None
  for owner in selected:
   b=owner.get('geometry')
   if not a or not b or row['literal']!=owner['literal'] or row['selection']['category']!=owner['selection']['category']:continue
   if row.get('source_sha256')!=owner.get('source_sha256'):continue
   if any(occurrences[(m['region_id'],m['literal'],m['selection']['category'])]>1 for m in (row,owner)):continue
   if set(row.get('region_ids',[row['region_id']])) & set(owner.get('region_ids',[owner['region_id']])):continue
   x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
   if x/max(1,min(a[2]-a[0],b[2]-b[0]))>=.85 and y/max(1,min(a[3]-a[1],b[3]-b[1]))>=.9:
    duplicate=owner;break
  if duplicate:
   row['duplicate_of']=duplicate['mention_id']
   duplicate.setdefault('duplicate_witnesses',[]).append({k:row.get(k) for k in ('mention_id','region_id','start','end','geometry','source_segments')})
  else:selected.append(row)
 return [m for m in mentions if not m.get('duplicate_of')]


def mark_duplicate_lines(regions):
 """Retain raw detector rows but interpret duplicated native lines once."""
 import re
 ordered=sorted([r for r in regions if r.get('geometry') and r.get('text')],
                key=lambda r:-len(re.sub(r'\s','',r['text'])))
 owners=[]
 for row in ordered:
  text=re.sub(r'\s','',row['text']);a=row['geometry']
  for owner in owners:
   b=owner['geometry'];other=re.sub(r'\s','',owner['text'])
   x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
   # Same column and mostly the same enclosure; adjacent columns never merge.
   if (text in other and x/max(1,max(a[2]-a[0],b[2]-b[0]))>=.7
       and x*y/max(1,(a[2]-a[0])*(a[3]-a[1]))>=.8):
    row.setdefault('context',{})['semantic_exclusion']={'reason':'duplicate_native_line',
        'owner_region_id':owner['region_id'],'literal_preserved':True}
    break
  else:owners.append(row)


def infer_figure_links(regions, native, dimensions):
 """Use entry markers, reading direction and caption bands as explicit evidence.

 These are reviewable layout inferences. No historical identity or chapter
 continuation is inferred from a nearby image.
 """
 import re
 figures=[b for b in native.get('blocks',[]) if b['type']=='figure' and b.get('geometry')]
 def area(b):return max(0,b[2]-b[0])*max(0,b[3]-b[1])
 def intersection(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
 # The detector emits both image groups and individual images. Keep leaves.
 leaves=[]
 for figure in sorted(figures,key=lambda b:area(b['geometry'])):
  a=figure['geometry']
  if any(intersection(a,b['geometry'])/max(1,area(b['geometry']))>=.85 for b in leaves):continue
  leaves.append(figure)
 width=dimensions[0] if dimensions else None
 # A bounded native image group can own a shared caption for front/back views.
 panels=[f for f in figures if width and f['geometry'][2]-f['geometry'][0]<width*.19
         and any(intersection(f['geometry'],b['geometry'])/max(1,area(b['geometry']))>=.85
                 for b in leaves)]
 panel_only={f['id'] for f in panels if f['id'] not in {b['id'] for b in leaves}}
 leaves += [f for f in panels if f['id'] in panel_only]
 def side(box):return int((box[0]+box[2])/2 >= width/2) if width else 0
 eligible=[r for r in regions if r.get('geometry') and r.get('text')
           and not r.get('context',{}).get('semantic_exclusion')]
 headings=[r for r in eligible if re.match(r'^\s*[◇◆◊○◯]',r['text'])]
 headings.sort(key=lambda r:-r['geometry'][0])
 # A running head can distinguish a continued earlier entry from the first
 # visible marked entry. It does not identify a specific historical person.
 headers=[r for r in eligible if r.get('role')=='running_header' or re.match(r'^\s*【[^】]*】',r['text'])]
 def entry_name(row):
  value=re.sub(r'\s','',row['text'])
  value=re.sub(r'^[◇◆◊○◯]','',value)
  from .semantic_groups import matched_spans,candidates
  names=[]
  for start,end in matched_spans(value):
   if start==0 and any(c['category']=='swordsmith_artisan' for c in candidates(value,start,end)):
    names.append(value[start:end])
  return names
 links=[]
 for figure in leaves:
  a=figure['geometry'];center=(a[0]+a[2])/2
  # A marked entry owns following material until the next marked entry.
  preceding=[r for r in headings if side(r['geometry'])==side(a) and r['geometry'][0]>center]
  if not preceding:
   first=next((r for r in headings if side(r['geometry'])==side(a)),None)
   header=next((r for r in headers if side(r['geometry'])==side(a)),None)
   names=entry_name(first) if first else []
   header_text=re.sub(r'^\s*【[^】]*】\s*','',header['text']).replace(' ','') if header else ''
   from .text_normalization import normalized
   if any(normalized(header_text).startswith(normalized(name)) for name in names):
    preceding=[first]
  if preceding and figure['id'] not in panel_only:
   heading=min(preceding,key=lambda r:abs(r['geometry'][0]-center))
   links.append({'text_region_id':heading['region_id'],'figure_id':figure['id'],
                 'relation':'entry_illustration','state':'layout_inferred',
                 'evidence':['printed_entry_marker','same_physical_page',
                             'bounded_entry_band','no_intervening_entry_marker',
                             *(['running_head_agrees_with_first_entry'] if heading['geometry'][0]<center else [])]})
  captions=[]
  for row in eligible:
   b=row['geometry'];text=re.sub(r'\s','',row['text'])
   cue=row.get('role')=='caption' or (len(text)<=12 and bool(re.search(r'銘|[歳歲]作|年作|年[頃比]|初期|晩年|[五互][ノの]目|丁子|[濤涛][亂乱]',text)))
   if not cue or side(a)!=side(b):continue
   overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))/max(1,b[2]-b[0])
   gap=b[1]-a[3]
   if overlap>=.7 and -max(20,(a[3]-a[1])*.2)<=gap<=max(120,(b[3]-b[1])):
    captions.append(row)
  for row in captions:
   links.append({'text_region_id':row['region_id'],'figure_id':figure['id'],
                 'relation':'figure_caption','state':'layout_inferred',
                 'evidence':['caption_class_or_printed_caption_cue','same_physical_page',
                             'shared_horizontal_footprint','adjacent_below_image']})
 # Multiple possible images for one caption stay explicit alternatives.
 for link in links:
  if link['relation']=='figure_caption':
   peers=[l for l in links if l['text_region_id']==link['text_region_id'] and l['relation']==link['relation']]
   boxes=[next(f['geometry'] for f in leaves if f['id']==l['figure_id']) for l in peers]
   # Nested group/member boxes are one panel; disjoint competing panels remain uncertain.
   common_parent=any(all(intersection(x,y)/max(1,area(y))>=.85 for y in boxes) for x in boxes)
   if not common_parent and any(not intersection(x,y) for x in boxes for y in boxes):link['state']='uncertain_candidate'
 return {'figures':leaves,'links':links,'state':'layout_proposals',
         'unknown_policy':'No marker/caption evidence means no asserted text-image link.'}

def document_groups(request,regions,payload):
 source=request.get('_retained_layout') or request.get('document_structure') or {}
 literal_source=source.get('source',{})
 docid=source.get('document_id') or request.get('document_id') or 'document:'+digest(canonical({'source':literal_source,'sha256':request.get('sha256'),'path':request.get('path'),'text':request.get('text')}))[:24]
 nodes=[{'id':docid,'type':'document','parent':None,'status':'source_metadata' if source.get('document_id') else 'derived_container_id','evidence':{'source':literal_source},'chapter_boundaries':'unknown' if not source.get('chapters') else 'explicit_source_metadata'}];edges=[];known={docid};context={}
 def node(ident,typ,parent,original,status='source_metadata'):
  ident=str(ident)
  if ident in known:
   return ident
  known.add(ident);nodes.append({'id':ident,'type':typ,'parent':parent,'status':status,'source_id':original.get('id') or original.get('paragraph_id') or original.get('region_id'),'page':original.get('page') or original.get('label') or source.get('label'),'geometry':original.get('geometry') or original.get('bbox') or original.get('rect'),'read_order':original.get('reading_order') or original.get('order'),'literal_text':original.get('literal_text') or original.get('reading_text') or original.get('text'),'literal_span':original.get('literal_span'),'source_fields':original,'evidence':{'layout_profile':source.get('profile'),'source':literal_source}});edges.append({'from':parent,'to':ident,'type':'contains','status':status});return ident
 for typ,key in [('chapter','chapters'),('section','sections')]:
  for i,item in enumerate(source.get(key,[])):
   ident=item.get('id') or item.get(typ+'_id');
   if ident:node(ident,typ,item.get('parent_id',docid),item)
 pageid=str(source.get('id') or source.get('page_id') or docid+':page:'+str(request.get('page',0)))
 node(pageid,'page',source.get('section_id') if source.get('section_id') in known else docid,{'id':pageid,'source':literal_source,'label':source.get('label'),'reading_order':source.get('region_reading_order')},'source_metadata' if source.get('id') else 'unknown_page_container')
 for i,p in enumerate(source.get('paragraphs',source.get('reading_units',[]))):
  parent=p.get('section_id')
  if parent and parent not in known:node(parent,'section',docid,{'id':parent,'boundary':'unknown','source':'paragraph section_id reference'},'source_reference_boundary_unknown')
  ident=p.get('paragraph_id') or p.get('unit_id') or p.get('id') or pageid+':paragraph:'+str(i)
  role=p.get('role','paragraph');typ='repeated_header_metadata' if role in ('running_header','page_header','running_head','header') else 'caption' if role=='caption' else 'paragraph'
  node(ident,typ,parent or pageid,p)
 tables=source.get('tables',[])
 if isinstance(tables,dict):tables=tables.get('tables',[])
 for ti,t in enumerate(tables):
  tid=node(t.get('table_id') or t.get('id') or pageid+':table:'+str(ti),'table',pageid,t)
  for ri,row in enumerate(t.get('rows',[])):
   rid=node(row.get('row_id') or tid+':row:'+str(ri),'table_row',tid,row)
   for ci,cell in enumerate(row.get('cells',[])):
    if not isinstance(cell,dict):cell={'text':cell}
    node(cell.get('cell_id') or rid+':cell:'+str(ci),'table_cell',rid,cell)
 for i,f in enumerate(source.get('figures',[])):node(f.get('figure_id') or f.get('id') or pageid+':figure:'+str(i),'figure',pageid,f)
 # Retain owner-composed links verbatim; unknown endpoints are not invented.
 for key in ['illustrated_graph','associations','caption_links','cross_page_links','continuations','paragraph_groups','carry_out_entry_id','entry_continuations']:
  value=source.get(key)
  if value:
   edges.append({'type':'source_association_payload','source_field':key,'payload':value,'status':'inherited_source_status','evidence':{'source':literal_source,'profile':source.get('profile')}})
 # Typed associations retain explicit endpoints and source status. A continuation
 # is not evidence that an image belongs to a paragraph.
 typed=[]
 def links(value,field):
  if isinstance(value,list):
   for item in value:links(item,field)
  elif isinstance(value,dict):
   left=value.get('from_id',value.get('from',value.get('figure_id')))
   right=value.get('to_id',value.get('to',value.get('paragraph_id',value.get('caption_id'))))
   if isinstance(left,str) and isinstance(right,str):
    typ=str(value.get('type',value.get('relation',field)))
    image=any(x in typ.lower() for x in ('image','figure','caption')) or any(n['id'] in (left,right) and n['type'] in ('figure','caption') for n in nodes)
    typed.append({'from':left,'to':right,'type':typ,'status':value.get('status','source_association_unadjudicated'),'endpoints_resolved':left in known and right in known,'image_association':image,'source_field':field,'evidence':value})
   for key,item in value.items():
    if isinstance(item,(dict,list)):links(item,field)
 for field in ['illustrated_graph','associations','caption_links','cross_page_links','continuations']:links(source.get(field),field)
 edges.extend(typed)
 # Native detector blocks are geometry proposals, never invented chapters.
 native=(payload or {}).get('native_layout',{}) if isinstance(payload,dict) else {}
 inferred=infer_figure_links(regions,native,(payload or {}).get('dimensions'))
 native_blocks={}
 for block in native.get('blocks',[]):
  ident=pageid+':'+block['id'];native_blocks[block['id']]=ident
  node(ident,block['type'],native_blocks.get(block.get('parent_id'),pageid),block,'native_detector_proposal')
 for link in inferred['links']:
  edges.append({'from':link['text_region_id'],'to':native_blocks[link['figure_id']],
                'type':link['relation'],'status':link['state'],'image_association':True,
                'evidence':link['evidence']})
 for r in regions:
  rid=str(r['region_id'])
  parent=r.get('context',{}).get('section_id') or native_blocks.get(r.get('native_block')) or pageid
  if parent not in known:parent=pageid
  gid=rid if rid in known else node(rid,r.get('role','region'),parent,r,'source_region' if r.get('geometry') else 'literal_block')
  resolved=[e for e in typed if e['image_association'] and e['endpoints_resolved'] and rid in (e['from'],e['to'])]
  candidates=[{'figure_id':native_blocks[l['figure_id']],'state':l['state'],
               'relation':l['relation'],'evidence':l['evidence']}
              for l in inferred['links'] if l['text_region_id']==rid]
  if r.get('role')=='caption' and r.get('geometry'):
   x0,y0,x1,y1=r['geometry']
   for block in native.get('blocks',[]):
    if block['type']!='figure' or not block.get('geometry'):continue
    a,b,c,d=block['geometry'];overlap=max(0,min(x1,c)-max(x0,a))
    # Caption cue + common page + aligned band + geometry, never nearest alone.
    if overlap and min(abs(y1-b),abs(d-y0))<max(y1-y0,d-b)*.5:
     candidate={'figure_id':native_blocks[block['id']],'state':'uncertain_candidate',
                'evidence':['native_caption_class','same_page','horizontal_overlap','adjacent_vertical_band'],
                'section_agreement':'unknown'}
     candidates.append(candidate);edges.append({'from':rid,'to':candidate['figure_id'],'type':'caption_figure_candidate',**candidate})
  context[rid]={'document_id':docid,'group_id':gid,'parent_id':parent,'section_id':r.get('context',{}).get('section_id'),
                'source_page':pageid,'role':r.get('role','unknown'),'grouping_version':VERSION,
                'association_status':'explicit_image_link' if resolved else 'uncertain_candidates' if candidates else 'unknown',
                'figure_candidates':candidates,'chapter_id':None}
 # Reading-order blocks retain native TEXTBLOCK boundaries. Separate ungrouped
 # lines remain independent; headings/captions/furniture never join body text.
 reading_blocks=[];buckets={}
 for region in regions:
  rid=region['region_id'];role=region.get('role','text_line')
  if region.get('context',{}).get('semantic_exclusion'):continue
  key=context[rid]['parent_id'] if region.get('native_block') and role=='text_line' else rid
  buckets.setdefault(key,[]).append(region)
 for key,items in buckets.items():
  vertical=all(r.get('orientation')=='vertical' for r in items)
  horizontal=all(r.get('orientation')=='horizontal' for r in items)
  if all(r.get('geometry') for r in items):
   items=sorted(items,key=(lambda r:(-r['geometry'][0],r['geometry'][1])) if vertical else (lambda r:(r['geometry'][1],r['geometry'][0])) if horizontal else (lambda r:r.get('native_order',0)))
  reading_blocks.append({'block_id':key,'region_ids':[r['region_id'] for r in items],
                         'orientation':'vertical' if vertical else 'horizontal' if horizontal else 'mixed_or_unknown',
                         'order_rule':'top_to_bottom_characters_then_columns_right_to_left' if vertical else 'native_horizontal_lines_top_to_bottom' if horizontal else 'native_order_uncertain',
                         'continuation_policy':'only_within_native_textblock_without_heading_caption_or_furniture'})
 image_known=any(e['image_association'] and e['endpoints_resolved'] for e in typed)
 return {'version':VERSION,'document_id':docid,'nodes':nodes,'edges':edges,'region_context':context,'reading_blocks':reading_blocks,
         'figure_analysis':inferred,
         'unknowns':{'chapter':'unknown' if not source.get('chapters') else None,'cross_page_continuation':'unknown' if not source.get('continuations') and not source.get('cross_page_links') else None,'image_body_association':None if image_known else 'unknown'},
         'identity':digest(canonical({'source':source,'nodes':nodes,'edges':edges,'version':VERSION}))}

def layout_regions(page):
 result=[]
 for i,p in enumerate(page.get('paragraphs',page.get('reading_units',[]))):
  text=p.get('reading_text') or p.get('literal_text') or p.get('ja') or p.get('text_effective_ja') or ''
  if text:result.append({'region_id':p.get('paragraph_id') or p.get('unit_id') or p.get('id') or 'paragraph:'+str(i),'text':text,'role':p.get('role','paragraph'),'origin':'retained_source_layout','geometry':p.get('bbox') or p.get('bbox_xyxy_original_px'),'context':{'section_id':p.get('section_id'),'source_regions':p.get('region_ids',[]),'source_review_state':p.get('japanese_reading_status',p.get('review_status','unknown'))}})
 return result

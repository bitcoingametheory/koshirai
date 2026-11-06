"""Typed constraints; absent context provides no evidence."""
from .text_normalization import normalized
FIELDS=('generation','province','school_phase','role','era')
def compare(request,witness):
    support=[];conflicts=[]
    for field in FIELDS:
        a=request.get(field);b=witness.get(field)
        if field=='era':
            a=a or request.get('raw_era');b=b or witness.get('raw_era')
        if a is not None and b is not None and a!='' and b!='':
            (support if normalized(str(a))==normalized(str(b)) else conflicts).append(field)
    def interval(c):
        start=c.get('date_start',c.get('active_start'));end=c.get('date_end',c.get('active_end'))
        if start in (None,'') or end in (None,''):return None
        try:
            pair=int(start),int(end)
            return pair if pair[0]<=pair[1] else None
        except (ValueError,TypeError):return None
    a,b=interval(request),interval(witness)
    if a and b:(support if max(a[0],b[0])<=min(a[1],b[1]) else conflicts).append('date_interval')
    return support,conflicts

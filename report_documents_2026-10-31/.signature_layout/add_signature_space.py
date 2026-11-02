from pathlib import Path
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import ArrayObject, FloatObject, DictionaryObject, IndirectObject, NameObject
import hashlib, json, re, logging
logging.getLogger("pypdf").setLevel(logging.ERROR)

base=Path(__file__).resolve().parent.parent
source=base/'Перевод_статьи_CIKM_2026.pdf'
out=base/'Перевод_статьи_CIKM_2026_место_для_подписей.pdf'
original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
r=PdfReader(source)
w=PdfWriter();w.clone_document_from_reader(r)
# Keep A4 and the footer baseline; uniformly scale the vector artwork around
# the lower page edge to reserve 35 mm above the original text.
height=float(r.pages[0].mediabox.height)
old_top=56.4045792
new_top=35*72/25.4
bottom_anchor=height-814.6063656
scale=(height-new_top-bottom_anchor)/(height-old_top-bottom_anchor)
tx=float(r.pages[0].mediabox.width)*(1-scale)/2
ty=bottom_anchor*(1-scale)
transform=Transformation((scale,0,0,scale,tx,ty))

def x(v): return FloatObject(float(v)*scale+tx)
def y(v): return FloatObject(float(v)*scale+ty)

annotation_count=0
for page in w.pages:
    page.add_transformation(transform)
    if '/Annots' in page:
        for ref in page['/Annots'].get_object():
            a=ref.get_object();annotation_count+=1
            if '/Rect' in a:
                z=a['/Rect'];a[NameObject('/Rect')]=ArrayObject([x(z[0]),y(z[1]),x(z[2]),y(z[3])])
            if '/QuadPoints' in a:
                a[NameObject('/QuadPoints')]=ArrayObject([x(v) if i%2==0 else y(v) for i,v in enumerate(a['/QuadPoints'])])
# Adjust internal link and outline destinations to their new positions.
seen=set()
def destinations(obj):
    if isinstance(obj,IndirectObject):
        key=(obj.idnum,obj.generation)
        if key in seen:return
        seen.add(key);obj=obj.get_object()
    elif isinstance(obj,(ArrayObject,DictionaryObject)):
        key=('direct',id(obj))
        if key in seen:return
        seen.add(key)
    else:return
    if isinstance(obj,ArrayObject):
        if len(obj)>1 and str(obj[1]) in {'/XYZ','/FitH','/FitBH','/FitV','/FitBV','/FitR'}:
            kind=str(obj[1])
            def numeric(i,fn):
                if len(obj)>i and isinstance(obj[i],(int,float)):
                    obj[i]=fn(obj[i])
            if kind=='/XYZ':numeric(2,x);numeric(3,y)
            elif kind in {'/FitH','/FitBH'}:numeric(2,y)
            elif kind in {'/FitV','/FitBV'}:numeric(2,x)
            elif kind=='/FitR':
                for i in [2,4]:numeric(i,x)
                for i in [3,5]:numeric(i,y)
            return
        for v in list(obj):destinations(v)
    else:
        for key,v in list(obj.items()):
            if key in {'/Names','/Dests','/Names','/Kids','/Outlines','/First','/Last','/Next','/Prev','/A','/D','/Dest'}:
                destinations(v)
destinations(w._root_object)
# Link actions on pages can contain explicit destinations as well.
for page in w.pages:
    if '/Annots' in page:
        for a in page['/Annots'].get_object():destinations(a)
w.add_metadata({'/Title':'Перевод статьи CIKM 2026 с местом для подписей'})
with out.open('wb') as f:w.write(f)
check=PdfReader(out)
assert len(check.pages)==len(r.pages)==17
assert all(re.sub(r"\s", "", p.extract_text())==re.sub(r"\s", "", q.extract_text()) for p,q in zip(r.pages,check.pages))
assert all(tuple(p.mediabox)==tuple(q.mediabox) for p,q in zip(r.pages,check.pages))
assert hashlib.sha256(source.read_bytes()).hexdigest()==original_hash
report={'source':str(source),'output':str(out),'pages':17,'top_space_mm':35,'uniform_scale':scale,'annotations_preserved':annotation_count,'page_size':'A4','text_identical':True,'source_unchanged':True}
(base/'.signature_layout/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))

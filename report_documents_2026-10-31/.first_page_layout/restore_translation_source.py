from pathlib import Path
import json,re,shutil
from pypdf import PdfReader,PdfWriter
from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
base=Path(__file__).parent.parent
work=base/'.titlepage_layout';work.mkdir(exist_ok=True)
log=Path('/Users/adpudovnikov/.codex/sessions/2026/10/31/rollout-2026-10-31T14-32-03-01a190a8-7e2b-7d92-bc70-ad28ebc8dfb5.jsonl')
chunks=[]
for line in log.read_text().splitlines():
    obj=json.loads(line);p=obj.get('payload',{})
    if obj.get('type')!='response_item' or p.get('type')!='custom_tool_call':continue
    code=p.get('input','')
    for match in re.finditer(r'cmd:("(?:\\.|[^"\\])*")',code):
        cmd=json.loads(match.group(1))
        if cmd.startswith("cat > 'report_documents_2026-10-31/.work/translation.tex'") or cmd.startswith("cat >> 'report_documents_2026-10-31/.work/translation.tex'"):
            chunks.append(cmd.split("<<'EOF'\n",1)[1].split('\nEOF',1)[0]+'\n')
assert len(chunks)==5
s=''.join(chunks)
s=s.replace('\\usepackage{enumitem}\n\\setlist{itemsep=2pt,topsep=5pt}\n','')
fontpath='/Users/adpudovnikov/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype/'
s=s.replace('\\setsansfont{DejaVu Sans}','\\setsansfont{DejaVuSans.ttf}[Path='+fontpath+']')
s=s.replace('\\setmonofont{DejaVu Sans Mono}[Scale=0.85]','\\setmonofont{DejaVuSansMono.ttf}[Path='+fontpath+',Scale=0.85]')
s=s.replace('с гарантиями отсутствия асимптотического сожаления','с гарантиями сублинейного сожаления').replace('Связанные правдивые контексты','Сходные контексты правдивого аукциона')
s=s.replace('У выбранной политики площадь под кривой нарушения бюджета (AUC) должна быть не хуже 1.05 от соответствующей величины для переноса исторической стационарной политики с масштабом 1.00.', 'У выбранной политики площадь под кривой нарушения бюджета (AUC) не должна превышать соответствующее значение для переноса исторической стационарной политики с масштабом 1.00, умноженное на 1.05.')
# Retain the recovered, previously verified text as the authoring baseline.
(work/'translation_original_layout.tex').write_text(s)
# Reserve a larger top field only on the first page; start the introduction with normal geometry on page 2.
s=s.replace('\\begin{document}\n','\\begin{document}\n\\newgeometry{left=22mm,right=22mm,top=35mm,bottom=21mm}\n',1)
s=s.replace('\\section{Введение}','\\restoregeometry\n\\section{Введение}',1)
(work/'translation.tex').write_text(s)
# Recover the final vector artwork directly from the verified PDF form objects.
figures=work/'figures';figures.mkdir(exist_ok=True)
r=PdfReader(base/'Перевод_статьи_CIKM_2026.pdf')
for page_idx,xname,filename in [(3,'/Fm0','idvc_workflow_surface_panel.pdf'),(10,'/Fm1','bat_selected_category_hour_dual_surfaces_clean.pdf'),(11,'/Fm2','warm_start_effect_forest.pdf')]:
    form=r.pages[page_idx]['/Resources']['/XObject'][xname].get_object()
    x0,y0,x1,y1=map(float,form['/BBox'])
    writer=PdfWriter();page=writer.add_blank_page(width=x1-x0,height=y1-y0)
    ref=writer._add_object(form.clone(writer))
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Art'):ref})})
    stream=DecodedStreamObject();stream.set_data(f'q 1 0 0 1 {-x0} {-y0} cm /Art Do Q'.encode('ascii'))
    page[NameObject('/Contents')]=writer._add_object(stream)
    with (figures/filename).open('wb') as f:writer.write(f)
original=Path('/Users/adpudovnikov/Downloads/coldstart_bidding2026cikm (4)')
shutil.copyfile(original/'cikm_implied_duals.bib',work/'cikm_implied_duals.bib')
bst=next((original/'acm_template').rglob('ACM-Reference-Format.bst'))
shutil.copyfile(bst,work/'ACM-Reference-Format.bst')
print('Restored source and final vector figures to',work)
print('Original two-line ORCID block retained; first-page top 35 mm; introduction forced to page 2.')

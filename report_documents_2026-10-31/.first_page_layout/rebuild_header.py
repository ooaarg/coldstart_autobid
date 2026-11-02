from pathlib import Path
from io import BytesIO
import hashlib,json,re
import pymupdf as pm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

base=Path(__file__).resolve().parent.parent
work=Path(__file__).parent
source=base/'Перевод_статьи_CIKM_2026.pdf'
out=base/'Перевод_статьи_CIKM_2026_подписи_перед_аннотацией.pdf'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
fonts=Path('/Users/adpudovnikov/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/Resources/fonts/truetype')
for name,file in [('LS','LiberationSerif-Regular.ttf'),('LSB','LiberationSerif-Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(fonts/file)))

doc=pm.open(source);pg=doc[0];W,H=pg.rect.width,pg.rect.height
# Keep the title, subtitle, abstract, and all body content at their original positions.
# Only the former author/ORCID/publication block is rebuilt.
for link in pg.get_links():
    if link['from'].intersects(pm.Rect(0,111,W,289)):pg.delete_link(link)
pg.add_redact_annot(pm.Rect(0,111,W,289),fill=(1,1,1),cross_out=False)
pg.apply_redactions(images=0,graphics=0,text=0)

stream=BytesIO();c=canvas.Canvas(stream,pagesize=(W,H),pageCompression=1)
link_specs=[]
def centered(text,baseline,size=9.9626,font='LS'):
    c.setFont(font,size);c.drawCentredString(W/2,H-baseline,text)
def runline(parts,baseline):
    width=sum(pdfmetrics.stringWidth(s,f,size) for s,f,size,offset in parts)
    xx=(W-width)/2
    for s,font,size,offset in parts:
        c.setFont(font,size);c.drawString(xx,H-baseline+offset,s)
        xx+=pdfmetrics.stringWidth(s,font,size)

venue='CIKM ’26, 7–11 ноября 2026 г., Рим, Италия. DOI: 10.1145/3799682.3841153.'
publication='ISBN: 979-8-4007-2539-5/2026/11. © 2026, авторы. Лицензия Creative Commons Attribution (CC BY).'
centered(venue,121,size=8)
centered(publication,131,size=8)
prefix='CIKM ’26, 7–11 ноября 2026 г., Рим, Италия. DOI: '
x=(W-pdfmetrics.stringWidth(venue,'LS',8))/2+pdfmetrics.stringWidth(prefix,'LS',8)
link_specs.append((pm.Rect(x,113.2,x+pdfmetrics.stringWidth('10.1145/3799682.3841153','LS',8),123),'https://doi.org/10.1145/3799682.3841153'))

names=[('Андрей Пудовиков','1,*'),('Александр Катруца','2'),('Егор Самосват','3'),('Юрий Дорн','1')]
parts=[]
for i,(name,sup) in enumerate(names):
    if i:parts.append((', ','LS',10.9091,0))
    parts.extend([(name,'LSB',10.9091,0),(sup,'LS',7.9701,4)])
runline(parts,147)
affiliations=[
 ('1','Институт искусственного интеллекта, МГУ имени М. В. Ломоносова, Москва, Россия',167.7),
 ('2','Центр искусственного интеллекта, МГУ имени М. В. Ломоносова, Москва, Россия',182.644),
 ('3','Независимый исследователь, Москва, Россия',197.588),
]
for sup,text,baseline in affiliations:
    runline([(sup,'LS',6.9738,3),(text,'LS',9.9626,0)],baseline)
email='pudovikovad@my.msu.ru';corresponding='Автор для переписки: '+email
runline([('*','LS',6.9738,3),(corresponding,'LS',9.9626,0)],212.532)
total=pdfmetrics.stringWidth('*','LS',6.9738)+pdfmetrics.stringWidth(corresponding,'LS',9.9626)
x=(W-total)/2+pdfmetrics.stringWidth('*','LS',6.9738)+pdfmetrics.stringWidth('Автор для переписки: ','LS',9.9626)
link_specs.append((pm.Rect(x,203.5,x+pdfmetrics.stringWidth(email,'LS',9.9626),215.0),'mailto:'+email))

left=62.362;right=W-left
c.setFont('LS',9.9626)
for baseline,l,r in [
 (227.476,'ORCID: А. Пудовиков — 0009-0008-0907-8396','А. Катруца — 0000-0002-7050-1615'),
 (242.420,'Е. Самосват — 0000-0003-3399-4235','Ю. Дорн — 0000-0003-0533-3018'),
]:
    c.drawString(left,H-baseline,l)
    c.drawRightString(right,H-baseline,r)
c.save()
header=pm.open(stream=stream.getvalue(),filetype='pdf')
pg.show_pdf_page(pg.rect,header,0)
for rect,uri in link_specs:pg.insert_link({'kind':pm.LINK_URI,'from':rect,'uri':uri})
metadata=dict(doc.metadata);metadata['title']='Перевод статьи CIKM 2026 с местом для подписей перед аннотацией';doc.set_metadata(metadata)
doc.save(out,garbage=4,deflate=True)
doc.close()
new=pm.open(out);old=pm.open(source)
assert len(new)==len(old)==17
# Other pages retain their original text and decoded drawing/text streams.
for i in range(1,17):
    assert new[i].get_text()==old[i].get_text(),i+1
    assert b''.join(new.xref_stream(x) for x in new[i].get_contents())==b''.join(old.xref_stream(x) for x in old[i].get_contents()),i+1
# The first-page body is untouched, including fonts, equations, spacing and footer.
for clip in [pm.Rect(0,0,W,110),pm.Rect(0,290,W,H)]:
    a=old[0].get_pixmap(matrix=pm.Matrix(2,2),clip=clip,alpha=False)
    b=new[0].get_pixmap(matrix=pm.Matrix(2,2),clip=clip,alpha=False)
    assert a.samples==b.samples,('first-page changed outside header',clip)
# Verify all original identifiers remain present.
s=new[0].get_text()
for text in ['0009-0008-0907-8396','0000-0002-7050-1615','0000-0003-3399-4235','0000-0003-0533-3018','10.1145/3799682.3841153','979-8-4007-2539-5/2026/11','pudovikovad@my.msu.ru']:
    assert text in s,text
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
new[0].get_pixmap(matrix=pm.Matrix(1.8,1.8),alpha=False).save(work/'first-page.png')
report={'output':str(out),'pages':17,'pages_2_to_17':'original content streams unchanged','first_page_title_and_body':'pixel-identical to original','ORCID':'two columns with wide horizontal gap','blank_space_before_abstract_mm':18,'original_pdf_unchanged':True}
(work/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))

from pathlib import Path
import re,pyphen
b=Path(__file__).parent
hyp=pyphen.Pyphen(lang='ru_RU')
for source,target in [('translation.tex','translation_typeset.tex'),('translation_original_layout.tex','baseline_typeset.tex')]:
 s=(b/source).read_text();head,body=s.split('\\begin{document}',1)
 body=re.sub(r'[А-Яа-яЁё]{5,}',lambda m:hyp.inserted(m.group(0),hyphen='\\-'),body)
 (b/target).write_text(head+'\\begin{document}'+body)

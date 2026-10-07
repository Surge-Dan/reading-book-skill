"""Source-preserving ebook parsing; no extraction to disk or silent clipping."""
import hashlib
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0; self.stack=[]; self.exclusions=[]
    def handle_starttag(self, tag, attrs):
        identity=(dict(attrs).get('id') or '').strip().lower()
        marker=identity in ('pg-header','pg-footer')
        suppress=tag in ('script','style') or marker
        if marker: self.exclusions.append({'kind':'gutenberg-boilerplate','wrapper_id':identity})
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.stack.append((tag,suppress))
            if suppress: self.hidden+=1
        if not self.hidden and tag in ('p','div','h1','h2','h3','li','br','tr'): self.parts.append('\n')
    def handle_endtag(self, tag):
        index=next((i for i in range(len(self.stack)-1,-1,-1) if self.stack[i][0]==tag),None)
        if index is not None:
            self.hidden-=sum(suppress for _,suppress in self.stack[index:]); del self.stack[index:]
        if not self.hidden and tag in ('p','div','h1','h2','h3','li','tr'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)

def _decode(data):
    encodings=['utf-8-sig']
    if data.startswith((b'\xff\xfe',b'\xfe\xff')): encodings.insert(0,'utf-16')
    encodings+=['gb18030']
    for encoding in encodings:
        try: return data.decode(encoding),encoding
        except UnicodeDecodeError: pass
    raise ValueError('Unsupported text encoding; export UTF-8 text.')

def parse_document(path):
    path=Path(path); raw=path.read_bytes(); source_hash=hashlib.sha256(raw).hexdigest()
    elements=[]; warnings=[]; exclusions=[]; title=path.stem; author=''; encoding=''; chapter=''
    def add(text,location):
        if text.strip():
            elements.append({'element_id':f'e{len(elements)+1:07d}', 'text':text, 'location':location,'chapter':chapter})
    suffix=path.suffix.lower()
    if suffix in ('.txt','.md'):
        text,encoding=_decode(raw)
        for line_no,line in enumerate(text.splitlines(keepends=True),1):
            if re.match(r'^#{1,6}\s|^第.{1,20}[章节卷部]',line): chapter=line.strip().lstrip('#').strip()
            add(line,f'{chapter + ": " if chapter else ""}line {line_no}')
    elif suffix=='.epub':
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist()
            if len(infos)>10000 or sum(i.file_size for i in infos)>100_000_000: raise ValueError('EPUB expanded size exceeds safe limit')
            for i in infos:
                if i.filename.startswith(('/','\\')) or '..' in i.filename.replace('\\','/').split('/'): raise ValueError('Unsafe EPUB archive path')
                if i.flag_bits & 1: raise ValueError('Encrypted EPUB is unsupported')
            container=ET.fromstring(archive.read('META-INF/container.xml'))
            rootfile=next(x for x in container.iter() if x.tag.endswith('rootfile')).attrib['full-path']
            package=ET.fromstring(archive.read(rootfile)); base=posixpath.dirname(rootfile)
            manifest={x.attrib['id']:x.attrib for x in package.iter() if x.tag.endswith('}item')}
            cover_hrefs={x.attrib.get('href','').split('#')[0] for x in package.iter() if x.tag.endswith('}reference') and x.attrib.get('type')=='cover'}
            for x in package.iter():
                if x.tag.endswith('}title') and x.text: title=x.text
                if x.tag.endswith('}creator') and x.text: author=x.text
            for item in (x for x in package.iter() if x.tag.endswith('}itemref')):
                entry=manifest[item.attrib['idref']]; href=entry['href'].split('#')[0]; name=posixpath.normpath(posixpath.join(base,href))
                if name.startswith('../') or name.startswith('/'): raise ValueError('Unsafe EPUB spine path')
                if 'nav' in entry.get('properties','').split() or href in cover_hrefs:
                    exclusions.append({'kind':'epub-navigation' if 'nav' in entry.get('properties','').split() else 'epub-cover','document':name}); continue
                parser=_HTML(); parser.feed(archive.read(name).decode('utf-8-sig')); chapter=name
                exclusions.extend(dict(exclusion,document=name) for exclusion in parser.exclusions)
                for paragraph,text in enumerate(''.join(parser.parts).splitlines(),1): add(text+'\n',f'{name}: paragraph {paragraph}')
    elif suffix=='.pdf':
        try:
            from pypdf import PdfReader
        except ImportError:
            try: from PyPDF2 import PdfReader
            except ImportError: raise ValueError('PDF parsing requires pypdf; install it or export text.')
        reader=PdfReader(str(path))
        if reader.is_encrypted: raise ValueError('Encrypted PDF is unsupported')
        for page_no,page in enumerate(reader.pages,1):
            chapter=f'page {page_no}'; text=page.extract_text() or ''
            if not text.strip(): warnings.append(f'page {page_no}: no text, possible scan; OCR required')
            add(text,chapter)
    else: raise ValueError('Supported formats: EPUB, PDF, TXT, MD')
    if not elements: raise ValueError('No readable body text; scanned PDFs require OCR.')
    return {'book':{'title':title,'author':author},'source_hash':source_hash,'elements':elements,'warnings':warnings,'exclusions':exclusions,'encoding':encoding}

def build_chunks(document,max_chars=12000):
    if max_chars<1: raise ValueError('max_chars must be positive')
    chunks=[]; current=[]; size=0; chapter=None
    def flush():
        nonlocal current,size
        if current: chunks.append({'chunk_id':f'c{len(chunks)+1:06d}','elements':current}); current=[]; size=0
    for element in document['elements']:
        if chapter!=element['chapter']: flush(); chapter=element['chapter']
        for offset in range(0,len(element['text']),max_chars):
            text=element['text'][offset:offset+max_chars]
            if size+len(text)>max_chars: flush()
            current.append(dict(element,text=text,offset=offset)); size+=len(text)
    flush(); return chunks

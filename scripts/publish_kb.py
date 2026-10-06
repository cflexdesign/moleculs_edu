#!/usr/bin/env python3
"""Publish the public knowledge base to Molecula's native CMS.

Secrets are read from a private Markdown file supplied with --access-file.
No tokens are written into the export, manifest, logs or repository.
Use --plan first, then --publish dev; production requires --publish prod.
Requires lxml; use the bundled workspace Python runtime.
"""
from __future__ import annotations
import argparse, collections, copy, hashlib, json, mimetypes, re, sys, time
import urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / 'outputs/knowledge-base'
WORK = ROOT / 'work/cms-publication'
ROUTES = ROOT / 'scripts/kb-routes.json'
BASES = {'dev':'https://cms.dev.mlcl.ru', 'prod':'https://cms.moleculai.ru'}
KINDS = {'Текст':'text', 'Изображения':'image', 'Картинки':'image', 'Видео':'video', 'Аудио':'audio'}

def norm(s):
    return re.sub(r'[^а-яa-z0-9]', '', s.lower().replace('ё', 'е'))

def slugify(s):
    letters = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                       ['a','b','v','g','d','e','e','zh','z','i','j','k','l','m','n','o','p','r','s','t','u','f','kh','ts','ch','sh','shch','','y','','e','yu','ya']))
    return re.sub(r'[^a-z0-9]+','-', ''.join(letters.get(c,c) for c in s.lower())).strip('-')

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def load(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default

def text(el):
    return ''.join(el.itertext()).strip()

def has(el, cls):
    return cls in el.get('class','').split()

def article(path):
    rows = html.parse(str(path)).xpath('//article')
    return rows[0] if rows else None

def redirect(path):
    rows = html.parse(str(path)).xpath('//meta[translate(@http-equiv,"REFSH","refsh")="refresh"]/@content')
    if not rows:return None
    match = re.search(r'url=(.*)', rows[0], re.I)
    return match.group(1) if match else None

def url(slug):
    return '/knowledge-base' + ('' if slug=='index' else '/'+slug)

def initialize_routes(rows):
    previous=load(ROUTES,{})
    existing = collections.defaultdict(list)
    for p in rows:existing[norm(p['title'])].append(p)
    mapping = previous.get('pages') or load(WORK/'original-slugs.json', {})
    mapping.update({'index.html':'index', 'program.html':'uchebnye-moduli', 'reference.html':'spravochnik'})
    for n in range(1,10):
        old = [p for p in rows if p['slug'].startswith(f'modul-{n:02d}-')]
        assert len(old)==1, (n,old)
        mapping[f'module-{n:02d}.html'] = old[0]['slug']
    for f in sorted(KB.glob('*.html')):
        if f.name in mapping:continue
        a=article(f)
        assert a is not None, f.name
        mapping[f.name] = slugify(text(a.xpath('./h1')[0]))
    anchors = {}; catalogs = {}
    for filename in ['004.html','005.html']:
        a=article(KB/filename)
        for el in a.xpath('.//details[contains(@class,"catalog-item")]'):
            title=text(el.xpath('./summary//strong')[0])
            matches=existing[norm(title)]
            if len(matches)>1:
                category=el.get('data-catalog-kind')
                if category=='Картинки':category='Изображения'
                matches=[p for p in matches if category in p.get('tags',[])]
            if not matches:
                # Display spelling can differ from an existing card (V5 / v5).
                category=el.get('data-catalog-kind')
                slug=slugify(title)
                if any(p['slug']==slug for p in rows):
                    raise ValueError('Ambiguous existing card: '+title)
            else:
                assert len(matches)==1, title
                slug=matches[0]['slug']
            key=filename+'#'+el.get('id')
            if key in previous.get('anchors',{}):slug=previous['anchors'][key]
            anchors[key]=slug
            catalogs[slug]={'filename':filename,'id':el.get('id'),'title':title,'category':el.get('data-catalog-kind')}
    # Retain links to earlier Suno anchors by taking them to the current version.
    for key in ['audio-model-02','audio-model-03','audio-model-04','audio-model-05']:
        anchors.setdefault('004.html#catalog-'+key, 'suno-v6')
    retired={'suno-v4-5-plus','suno-v4-5','suno-v4','suno-v3-5'}
    # Own only the original section pages, never arbitrary pages later added by another editor.
    original=load(WORK/'prod-full.json',rows)
    groups=previous.get('groups')
    if groups is None:
        groups=sorted({p['slug'] for p in original}-set(mapping.values())-set(catalogs)-retired)
    data={'pages':mapping,'anchors':anchors,'catalogs':catalogs,'groups':groups}
    save(ROUTES,data)
    return data

class Converter:
    def __init__(self, routes, media):
        self.routes=routes;self.media=media;self.file='';self.mode='text';self.prompts=[];self.unmapped=[]

    def link(self, href):
        if not href:return ''
        parts=urllib.parse.urlsplit(href)
        if parts.scheme in ['http','https']:
            assert parts.hostname=='moleculai.ru', 'External URL '+href
            return href
        if href.startswith('#'):
            anchored=self.file.split('#')[0]+href
            return url(self.routes['anchors'][anchored]) if anchored in self.routes['anchors'] else href
        key=Path(parts.path).name
        anchored=key+'#'+parts.fragment
        if anchored in self.routes['anchors']:return url(self.routes['anchors'][anchored])
        if key in self.routes['pages']:
            # Native Markdown heading ids differ from static HTML ids.
            return url(self.routes['pages'][key])
        local=(KB/parts.path).resolve()
        if local.exists() and local.is_file() and local.is_relative_to(ROOT/'outputs'):
            ref=self.media.get(str(local.relative_to(ROOT)))
            return ref['url'] if ref else 'asset:'+str(local.relative_to(ROOT))
        self.unmapped.append((self.file,href));return href

    def inline(self, el):
        if el.tag in ['button','input','script','style','form']:return ''
        if el.get('data-learning-progress') is not None or el.get('data-module-state') is not None:return ''
        if has(el,'image-expand'):return ''
        if el.tag=='br':return '\n'
        inner=(el.text or '')+''.join(self.inline(c)+(c.tail or '') for c in el)
        if el.tag in ['strong','b']:return '**'+inner.strip()+'**' if inner.strip() else ''
        if el.tag in ['em','i']:return '*'+inner.strip()+'*' if inner.strip() else ''
        if el.tag=='small':return ' — '+inner.strip()
        if el.tag=='code':return '`'+inner+'`'
        if el.tag=='a':return '['+inner.strip()+']('+self.link(el.get('href'))+')' if inner.strip() else ''
        return inner

    def markdown(self, el):
        tag=el.tag
        if tag in ['h1','script','style','button','input','form']:return ''
        if tag in ['h2','h3','h4','h5','h6']:return '#'*int(tag[1])+' '+self.inline(el)+'\n\n'
        if tag in ['p','figcaption','blockquote']:
            value=self.inline(el).strip()
            return ('> ' if tag=='blockquote' else '')+value+'\n\n' if value else ''
        if tag in ['ol','ul']:
            result=[]
            for i,li in enumerate(el.xpath('./li'),1):
                result.append((str(i)+'. ' if tag=='ol' else '- ')+self.inline(li).strip())
            return '\n'.join(result)+'\n\n'
        if tag=='table':
            rows=[[self.inline(c).replace('|','\\|').replace('\n',' ') for c in row.xpath('./th|./td')] for row in el.xpath('.//tr')]
            if not rows:return ''
            count=max(map(len,rows));rows=[row+['']*(count-len(row)) for row in rows]
            return '\n'.join('| '+' | '.join(row)+' |' for row in [rows[0],['---']*count]+rows[1:])+'\n\n'
        if tag=='a':return self.inline(el)+'\n\n'
        if has(el,'preserve-lines'):return self.inline(el).replace('\n','  \n')+'\n\n'
        return (el.text.strip()+'\n\n' if el.text and el.text.strip() else '')+''.join(self.markdown(c) for c in el)

    def blocks(self, node, filename, mode='text'):
        self.file=filename;self.mode=mode
        result=[];buffer=[]
        def flush():
            body=''.join(buffer).strip();buffer.clear()
            body=body.replace('отметьте выполнение','сохраните результат').replace('отметьте его выполненным','сохраните принятую версию')
            body=body.replace('Сохраните принятую версию и сохраните результат.', 'Сохраните принятую версию.')
            body=body.replace('Отметки можно восстановить по сохранённому коду.', '')
            if body:result.append({'__component':'kb.markdown','body':body})
        def visit(el):
            if not isinstance(el.tag,str):return
            if el.tag in ['h1','button','input','script','style'] or has(el,'task-done') or has(el,'portable-progress'):return
            if el.get('data-learning-progress') is not None or el.get('data-learning-resume') is not None:return
            if has(el,'single-check'):
                flush();form=el.xpath('.//form')[0];legend=text(form.xpath('.//legend')[0]);options=[text(v) for v in form.xpath('.//label/span')]
                intro=' '.join(text(p) for p in form.xpath('./fieldset/p'))
                question=(intro+'\n\n' if intro else '')+'\n'.join(f'{i}. {v}' for i,v in enumerate(options,1))
                result.append({'__component':'kb.markdown','body':'## Проверьте себя\n\n'+legend+'\n\n'+question})
                i=int(form.get('data-correct'));explanation=text(form.xpath('.//p[contains(@class,"quiz-explanation")]')[0])
                result.append({'__component':'kb.faq','title':'Разбор ответа','items':[{'question':'Показать правильный ответ','answer':f'Вариант {i+1}: {options[i]}\n\n'+explanation}]})
                return
            if has(el,'directory-grid'):
                flush();items=[]
                for a in el.xpath('./a'):
                    h=a.xpath('./h2');p=a.xpath('./p')
                    items.append({'title':text(h[0]) if h else text(a),'text':text(p[0]) if p else '', 'url':self.link(a.get('href'))})
                if items:result.append({'__component':'kb.cards','title':'','columns':'2','items':items})
                return
            if el.tag=='pre':
                value=text(el)
                if value:
                    flush();title='Запрос';previous=el.getprevious()
                    if previous is not None and previous.tag in ['h2','h3','h4']:title=text(previous)
                    prompt_mode=el.get('data-mode',mode)
                    assert prompt_mode in ['text','image','video','audio'],(filename,prompt_mode)
                    result.append({'__component':'kb.prompt','title':title,'prompt':value,'mode':prompt_mode})
                    self.prompts.append((filename,value))
                return
            if el.tag=='figure' or el.tag in ['img','audio','video']:
                targets=[el] if el.tag in ['img','audio','video'] else el.xpath('.//img|.//audio|.//video')
                if not targets:
                    buffer.append(self.markdown(el));return
                flush()
                caption=' '.join(text(c) for c in el.xpath('.//figcaption'))
                for target in targets:
                    src=target.get('src') or next(iter(target.xpath('./source/@src')),None)
                    if not src:continue
                    local=(KB/src).resolve();key=str(local.relative_to(ROOT));ref=self.media.get(key)
                    if target.tag=='audio':
                        result.append({'__component':'kb.markdown','body':'['+(caption or 'Прослушать учебный аудиофайл')+']('+(ref['url'] if ref else 'asset:'+key)+')'})
                    else:
                        result.append({'__component':'kb.media','file':ref['id'] if ref else 'asset:'+key,'caption':caption,'alt':target.get('alt') or caption or 'Учебный пример'})
                return
            if el.tag=='details':
                flush();summary=el.xpath('./summary');body=copy.deepcopy(el)
                for s in body.xpath('./summary'):s.getparent().remove(s)
                # Preserve nested prompts/media in catalog-style or instructional details.
                if body.xpath('.//pre|.//img|.//video|.//audio'):
                    if summary:buffer.append('## '+text(summary[0])+'\n\n')
                    for child in body:visit(child)
                else:
                    result.append({'__component':'kb.faq','title':'','items':[{'question':text(summary[0]) if summary else 'Подробнее','answer':self.markdown(body).strip()}]})
                return
            if has(el,'note'):
                flush();result.append({'__component':'kb.callout','tone':'info','title':'','body':self.markdown(el).strip()});return
            if el.xpath('.//pre|.//figure|.//video|.//audio|.//img|.//form|.//details'):
                if el.text and el.text.strip():buffer.append(el.text+'\n\n')
                for child in el:visit(child)
            else:buffer.append(self.markdown(el))
        for child in node:visit(child)
        flush()
        return result

def build_plan(rows, media):
    routes=initialize_routes(rows);conv=Converter(routes,media)
    user_guides=load(ROOT/'scripts/user-guide-routes.json',{})
    legacy_slugs={p['slug'] for p in load(WORK/'prod-full.json',rows)}
    byslug={p['slug']:p for p in rows};bydoc={p['documentId']:p['slug'] for p in rows}
    plans={}
    def add(slug,title,blocks,summary='',parent=None,order=0,tags=None,visible=True):
        old=byslug.get(slug,{})
        if parent is None and old.get('parent'):parent=bydoc[old['parent']['documentId']]
        plans[slug]={'title':title,'navTitle':title,'slug':slug,'summary':summary,'parent':parent,
                     'order':order if order else old.get('order',0),'showInNav':visible,'tags':tags or [],
                     'blocks':blocks,'seoTitle':title+' · Молекула','seoDescription':summary[:160] or title}
    for f in sorted(KB.glob('*.html')):
        slug=routes['pages'][f.name];a=article(f);dest=redirect(f)
        if dest:
            target=conv.link(dest)
            title=byslug.get(slug,{}).get('title') or slug
            add(slug,title,[{'__component':'kb.cta','title':'Открыть актуальную инструкцию','text':'Этот материал перенесён. Перейдите к обновлённой странице.','buttonLabel':'Открыть инструкцию','url':target}],visible=False)
            continue
        title=text(a.xpath('./h1')[0]);lead=a.xpath('./p[contains(@class,"lead")]')
        summary=text(lead[0]) if lead else ''
        body=copy.deepcopy(a)
        # The CMS shell already renders H1 and summary.
        for p in body.xpath('./p[contains(@class,"lead")]'):p.getparent().remove(p)
        if f.name in ['004.html','005.html']:
            for section in body.xpath('./section[contains(@class,"kb-model-catalog")]'):section.getparent().remove(section)
        match=re.fullmatch(r'module-(\d\d)-(\d).html',f.name)
        parent=routes['pages']['module-'+match[1]+'.html'] if match else None
        if f.name=='reference.html':parent='index'
        if f.name=='program.html':parent='index'
        if f.name=='004.html' or f.name=='005.html':parent=routes['pages']['reference.html']
        mode='audio' if f.name=='module-08-1.html' or f.name in ['072.html','075.html'] else 'text'
        if f.name in ['module-05-1.html','module-05-3.html'] or f.name in ['040.html','041.html','042.html','043.html','044.html','045.html']:mode='image'
        if f.name in ['module-07-1.html','051.html','059.html','060.html']:mode='video'
        blocks=conv.blocks(body,f.name,mode)
        if f.name=='index.html':
            blocks=[{'__component':'kb.cta','title':'Первый чат','text':'Напишите короткое сообщение, получите ответ и попробуйте одну правку. Пример уже заполнен, свои файлы не нужны.','buttonLabel':'Попробовать первый чат','url':url(routes['pages']['003.html'])},
                    {'__component':'kb.cards','title':'Что хотите сделать?','columns':'2','items':[
                        {'title':label,'text':description,'url':url(routes['pages'][file])} for file,label,description in [
                            ('text-life.html','Написать сообщение','Письмо, приглашение или небольшой план.'),
                            ('text-study.html','Разобраться в теме','Объяснение и вопросы для проверки себя.'),
                            ('text-resume.html','Подготовить резюме','Реальный опыт и тренировка интервью.'),
                            ('image-first.html','Создать изображение','Сцена, свет и композиция.'),
                            ('image-marketplace.html','Сделать карточки товара','Реальное фото, свойства и подписи.'),
                            ('video-first.html','Оживить фотографию','Один кадр и одно движение.'),
                            ('072.html','Создать музыку','Описание, стиль и вокал.'),
                            ('text-presentation.html','Подготовить презентацию','Содержание слайдов и речь.')]]}]
        add(slug,title,blocks,summary,parent,int(match[2]) if match else 0,['Обучение'] if match or f.name.startswith('module-') else [],visible=f.name!='index.html')
        # Existing relations stay stable. Only new guides receive an explicit section.
        if f.name in user_guides and slug not in legacy_slugs:
            plans[slug]['parent']=user_guides[f.name]['parent']
        if f.name=='003.html':plans[slug]['order']=-10
        if f.name in user_guides:plans[slug]['tags']=['Инструкция']
    for slug,meta in routes['catalogs'].items():
        a=article(KB/meta['filename']);el=a.xpath('.//details[@id="'+meta['id']+'"]')[0]
        body=copy.deepcopy(el.xpath('./div[contains(@class,"catalog-body")]')[0])
        mode=KINDS.get(meta['category'],'text')
        summary=text(body.xpath('./p')[0])
        # The native page header already displays this description.
        first_paragraph=body.xpath('./p')[0]
        if len(body)>1:body.remove(first_paragraph)
        else:summary=''
        old=byslug.get(slug)
        parent=bydoc[old['parent']['documentId']] if old and old.get('parent') else {
            'text':'modeli-molekuly-tekst','image':'modeli-molekuly-izobrazheniya',
            'video':'modeli-molekuly-video','audio':'modeli-molekuly-audio'}[mode]
        blocks=conv.blocks(body,meta['filename']+'#'+meta['id'],mode)
        add(slug,meta['title'],blocks,summary,parent,tags=['Роли' if meta['filename']=='005.html' else 'Модели',meta['category']])
    # Keep withdrawn model URLs usable, but remove them from navigation.
    for slug in ['suno-v4-5-plus','suno-v4-5','suno-v4','suno-v3-5']:
        old=byslug.get(slug)
        if old:add(slug,old['title'],[{'__component':'kb.cta','title':'Актуальная версия Suno','text':'В обучении используется меню с Suno v6.','buttonLabel':'Открыть Suno v6','url':url('suno-v6')}],visible=False)
    # Group pages keep their stable addresses; rebuild cards from current visible children.
    group_slugs=set(routes['groups'])-set(plans)
    for slug in group_slugs:
        p=byslug[slug]
        add(slug,p['title'],[],p.get('summary') or '',tags=[])
    # Tool-oriented navigation mirrors the user's mental model, not the old business-first syllabus.
    roots={
        'nachalo-raboty':('С чего начать',0,'Первый чат, выбор модели, файлы и понятные запросы.'),
        'tekst-i-yazykovye-modeli':('Текст и языковые модели',1,'Учёба, переписка, работа, документы и модели для текста.'),
        'izobrazheniya':('Изображения',2,'Создание сцен, свои фотографии, стили и карточки товаров.'),
        'video':('Видео',3,'Исходный кадр, движение, шаблоны и короткая история.'),
        'avatary':('Аватары',4,'Портрет, движение и проверка говорящего ведущего.'),
        'audio':('Аудио',5,'Музыка, свои слова и голосовой ввод.'),
        'roli-dlya-biznesa':('Роли',6,'Помощники для учёбы, работы, публикаций и творческих задач.'),
        'proekty-i-materialy':('Проекты и файлы',7,'Материалы одной темы и разговоры по документам.'),
    }
    for slug,(title,order,summary) in roots.items():
        if slug in plans:
            plans[slug].update(title=title,navTitle=title,order=order,summary=summary,
                               seoTitle=title+' · Молекула',seoDescription=summary)
    # Place newly split instructions beside their original article.
    for f,slug in routes['pages'].items():
        if slug not in plans or f.startswith('module-') or f in ['index.html','program.html','reference.html']:continue
        if slug not in byslug and '-' in f and f not in user_guides:
            original=routes['pages'].get(f.split('-')[0]+'.html')
            if original and original in plans:plans[slug]['parent']=plans[original]['parent']
        if plans[slug]['parent'] is None:plans[slug]['parent']=routes['pages']['reference.html']
    def depth(slug):
        seen={slug};count=0;parent=plans[slug]['parent']
        while parent:
            assert parent not in seen, 'Cycle: '+slug
            seen.add(parent);count+=1;parent=plans[parent]['parent']
        return count
    # Resolve empty child groups before parents. Set iteration would make cards nondeterministic.
    for slug in sorted(group_slugs,key=lambda s:(-depth(s),s)):
        children=sorted((p for p in plans.values() if p['parent']==slug and p['showInNav']),key=lambda p:(p['order'],p['title']))
        if children:
            plans[slug]['blocks']=[{'__component':'kb.cards','title':'Материалы раздела','columns':'2','items':[{'title':p['title'],'text':p['summary'],'url':url(p['slug'])} for p in children]}]
        else:
            plans[slug]['showInNav']=False
            plans[slug]['blocks']=[{'__component':'kb.cta','title':'Выберите нужную инструкцию','text':'Актуальные материалы собраны в справочнике.','buttonLabel':'Открыть справочник','url':url(routes['pages']['reference.html'])}]
    for catalog in ['004.html','005.html']:
        category_slugs=sorted(set(plans[s]['parent'] for s,m in routes['catalogs'].items() if m['filename']==catalog))
        plans[routes['pages'][catalog]]['blocks'].append({'__component':'kb.cards','title':'Открыть раздел каталога','columns':'2','items':[{'title':plans[s]['title'],'text':'Карточки с описанием, полным запросом и проверкой результата.','url':url(s)} for s in category_slugs]})
    # Ensure index is root (never make a cycle with the reference page).
    plans['index']['parent']=None
    # The home page is hidden from the tree; visible navigation roots must not be its children.
    plans[routes['pages']['program.html']]['parent']=None
    plans[routes['pages']['reference.html']]['parent']=None
    plans[routes['pages']['program.html']]['order']=8
    plans[routes['pages']['program.html']]['navTitle']='Практика для бизнеса'
    plans[routes['pages']['reference.html']]['order']=100
    assert not conv.unmapped, conv.unmapped
    for slug,p in plans.items():
        assert p['blocks'], slug
        if p['parent']:assert p['parent'] in plans,(slug,p['parent'])
        if p['showInNav'] and p['parent']:assert plans[p['parent']]['showInNav'],(slug,'Hidden parent')
        seen={slug};parent=p['parent']
        while parent:
            assert parent not in seen, 'Cycle: '+slug
            seen.add(parent);parent=plans[parent]['parent']
        for b in p['blocks']:
            if b['__component']=='kb.prompt':assert b['prompt'].strip(),slug
        for link in re.findall(r'/knowledge-base(?:/([a-z0-9-]+))?',json.dumps(p,ensure_ascii=False)):
            assert (link or 'index') in plans, (slug,'Missing target',link)
    save(WORK/'export.json',plans)
    save(WORK/'source-prompts.json',conv.prompts)
    return plans

class Client:
    def __init__(self, env, access):
        self.env=env;self.base=BASES[env]
        match=re.search(re.escape(self.base)+r'\s*\|\s*`([^`]+)`',access.read_text())
        if not match:raise ValueError('No credential for '+env)
        self.token=match.group(1)

    def request(self,path,query=None,data=None,method='GET',binary=None,content_type=None):
        endpoint=self.base+path+('?' +urllib.parse.urlencode(query) if query else '')
        headers={'Authorization':'Bearer '+self.token}
        body=binary
        if data is not None:body=json.dumps(data,ensure_ascii=False).encode();headers['Content-Type']='application/json'
        if content_type:headers['Content-Type']=content_type
        req=urllib.request.Request(endpoint,headers=headers,data=body,method=method)
        try:
            with urllib.request.urlopen(req,timeout=60) as res:return json.load(res)
        except urllib.error.HTTPError as e:
            # Server error response contains validation details, never request headers.
            detail=e.read().decode(errors='replace')
            detail=detail.replace(self.token,'[redacted]')
            raise RuntimeError(f'{method} {path}: HTTP {e.code} {detail[:1800]}') from None

    def inventory(self):
        rows=[];page=1
        while True:
            q={'locale':'ru','status':'published','pagination[pageSize]':100,'pagination[page]':page,'sort':'slug:asc','populate[parent][fields][0]':'slug','populate[blocks][populate]':'*','populate[icon]':'true'}
            response=self.request('/api/kb-pages',q);rows.extend(response['data'])
            if page>=response['meta']['pagination']['pageCount']:return rows
            page+=1

    def upload(self,path):
        boundary='molecula-'+uuid.uuid4().hex
        mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        header=(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{path.name}"\r\nContent-Type: {mime}\r\n\r\n').encode()
        data=header+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
        return self.request('/api/upload',method='POST',binary=data,content_type='multipart/form-data; boundary='+boundary)[0]

def assets(plan):
    found=set()
    for match in re.finditer(r'asset:([^"\s)]+)',json.dumps(plan,ensure_ascii=False)):
        found.add(match.group(1))
    return found

def media_map(client, plans):
    registry_path=WORK/(client.env+'-media.json');registry=load(registry_path,{})
    uploads=client.request('/api/upload/files',{'pagination[pageSize]':1000})
    files={u['name']:u for u in uploads}
    for key in sorted(assets(plans)):
        path=(ROOT/key).resolve()
        assert path.is_relative_to(ROOT/'outputs') and path.is_file(),key
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        if key in registry and registry[key].get('sha256')==sha:continue
        # Existing KB assets retain original names and sizes. Reuse only a unique exact match.
        candidates=[u for u in uploads if u['name']==path.name and abs(u['size']*1000-path.stat().st_size)<2]
        u=candidates[0] if len(candidates)==1 else client.upload(path)
        asset_url=u['url'] if u['url'].startswith('https://') else client.base+u['url']
        registry[key]={'id':u['id'],'url':asset_url,'sha256':sha,'name':path.name}
        save(registry_path,registry)
        print('media',client.env,path.name,'reused' if len(candidates)==1 else 'uploaded',flush=True)
    return registry

def fingerprint(p):
    return hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def publish(client, plans, rows, select=None):
    registry_path=WORK/(client.env+'-published.json');registry=load(registry_path,{})
    documents={r['slug']:r['documentId'] for r in rows}
    targets=set(select or plans)
    assert targets<=plans.keys(),targets-plans.keys()
    # Create new pages first, so every relation has a valid documentId.
    for slug in sorted(targets):
        if slug not in documents:
            p=plans[slug]
            response=client.request('/api/kb-pages',{'locale':'ru','status':'published'},data={'data':{k:v for k,v in p.items() if k!='parent'}},method='POST')
            documents[slug]=response['data']['documentId']
            save(WORK/(client.env+'-documents.json'),documents)
            print('created',client.env,slug,flush=True)
    updated=skipped=0
    for slug in sorted(targets):
        p=copy.deepcopy(plans[slug]);sha=fingerprint(p)
        if registry.get(slug,{}).get('sha256')==sha:
            skipped+=1;continue
        parent=p['parent']
        if parent and parent not in documents:raise ValueError('Missing parent '+parent)
        p['parent']=documents[parent] if parent else None
        response=client.request('/api/kb-pages/'+documents[slug],{'locale':'ru','status':'published'},data={'data':p},method='PUT')
        assert response['data']['slug']==slug
        registry[slug]={'sha256':sha,'documentId':documents[slug],'updatedAt':response['data'].get('updatedAt')}
        save(registry_path,registry);updated+=1
        if updated%15==0:print('published',client.env,updated,'pages',flush=True)
    print('publication',client.env,{'updated':updated,'unchanged':skipped,'selected':len(targets)},flush=True)

def verify(client,plans,targets):
    rows=client.inventory();actual={p['slug']:p for p in rows};errors=[]
    bydoc={p['documentId']:p['slug'] for p in rows}
    for slug in targets:
        p=plans[slug];r=actual.get(slug)
        if not r:errors.append((slug,'missing'));continue
        for key in ['title','navTitle','summary','order','tags','showInNav','seoTitle','seoDescription']:
            if r.get(key)!=p.get(key):errors.append((slug,key))
        parent=bydoc.get((r.get('parent') or {}).get('documentId'))
        if parent!=p['parent']:errors.append((slug,'parent'))
        def clean(v):
            if isinstance(v,list):return [clean(x) for x in v]
            if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k!='id' and x is not None}
            return v
        got=clean(r['blocks']);want=clean(p['blocks'])
        for b in got:
            if b['__component']=='kb.media' and isinstance(b.get('file'),dict):b['file']=next(x['file'] for x in r['blocks'] if x['__component']=='kb.media' and x['file']['documentId']==b['file']['documentId'])['id']
        # Strapi adds optional schema defaults. Compare only fields submitted by this publisher.
        if len(got)!=len(want):errors.append((slug,'block-count'));continue
        for i,(g,w) in enumerate(zip(got,want)):
            for k,v in w.items():
                if g.get(k)!=v:errors.append((slug,'block-'+str(i)+'-'+k))
    report={'environment':client.env,'pagesInCms':len(rows),'verified':len(targets),'errors':errors}
    save(WORK/(client.env+'-verification.json'),report)
    if errors:raise ValueError(str(errors[:25]))
    print('verified',report,flush=True)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--publish',choices=BASES)
    parser.add_argument('--verify',choices=BASES)
    parser.add_argument('--access-file',type=Path)
    parser.add_argument('--only',nargs='+')
    args=parser.parse_args();WORK.mkdir(parents=True,exist_ok=True)
    if args.plan:
        rows=load(WORK/'prod-full.json')
        if not rows and args.access_file:
            rows=Client('prod',args.access_file).inventory();save(WORK/'prod-full.json',rows)
        assert rows,'Use --plan --access-file PATH to retrieve a CMS backup on first setup.'
        plans=build_plan(rows,{})
        print('plan',{'pages':len(plans),'visible':sum(p['showInNav'] for p in plans.values()),'prompts':sum(b['__component']=='kb.prompt' for p in plans.values() for b in p['blocks']),'assets':len(assets(plans))})
        return
    assert args.access_file and (args.publish or args.verify),'Use --plan or select an environment with --access-file.'
    env=args.publish or args.verify;client=Client(env,args.access_file)
    rows=client.inventory();backup=WORK/f'{env}-backup-{time.strftime("%Y%m%d-%H%M%S")}.json';save(backup,rows)
    # Relations and metadata are resolved against a fresh inventory, never reused documentIds.
    baseline=rows
    plans=build_plan(baseline,load(WORK/(env+'-media.json'),{}))
    targets=args.only or list(plans)
    if args.publish:
        selected={s:plans[s] for s in targets}
        registry=media_map(client,selected)
        plans=build_plan(baseline,registry)
        assert not assets({s:plans[s] for s in targets}),'Unresolved asset'
        publish(client,plans,rows,args.only)
    verify(client,plans,targets)

if __name__=='__main__':main()

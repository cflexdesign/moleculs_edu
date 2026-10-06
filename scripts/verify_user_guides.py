#!/usr/bin/env python3
"""Acceptance checks for human teaching pages, links, prompts and CMS conversion."""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import json,re,sys,hashlib,subprocess
from lxml import html
from user_guide_content import GUIDES,ROLE_LESSONS
import publish_kb

ROOT=Path(__file__).resolve().parents[1];KB=ROOT/'outputs/knowledge-base'
errors=[]
def check(ok,msg):
    if not ok:errors.append(msg)
docs={};target_cache={};articles=0;redirects=0;prompts=0
for f in (ROOT/'outputs').glob('*/*.html'):
    d=html.parse(str(f));docs[f]=d
    redirect=d.xpath('//meta[translate(@http-equiv,"REFSH","refsh")="refresh"]')
    if redirect:redirects+=1
    else:
        check(len(d.xpath('//h1'))==1,f.name+': h1')
        check(bool(d.xpath('//main')),f.name+': main')
        if f.parent==KB:articles+=1
    ids=d.xpath('//@id');check(len(ids)==len(set(ids)),str(f)+': duplicate ids')
    for b in d.xpath('//*[@data-copy]'):
        target=b.get('data-copy')
        if target:check(bool(d.xpath('//*[@id=$id]',id=target)),str(f)+': copy target '+target)
    for node in d.xpath('//*[@href or @src]'):
        address=node.get('href') or node.get('src');u=urlsplit(address)
        if u.scheme or u.netloc:
            check(u.scheme=='https' and u.hostname in ['moleculai.ru','www.moleculai.ru'],str(f)+': external link '+address)
        else:
            target=(f.parent/unquote(u.path)).resolve() if u.path else f
            check(target.is_file(),str(f)+': missing '+address)
            if target.is_file() and target.suffix=='.html' and u.fragment:
                if target not in target_cache:target_cache[target]=set(html.parse(str(target)).xpath('//@id'))
                alias={'catalog-audio-suno-v45-plus':'catalog-audio-suno-v6','catalog-audio-suno-v45':'catalog-audio-suno-v6','catalog-audio-suno-v4':'catalog-audio-suno-v6','catalog-audio-suno-v35':'catalog-audio-suno-v6'}.get(u.fragment,u.fragment)
                check(alias in target_cache[target],str(f)+': fragment '+address)
    check(not re.search(r'info@moleculai|Nexgig|Bearer\s+|sk-[a-zA-Z0-9]{20}',f.read_text()),str(f)+': secret or account data')
    for pre in d.xpath('//article//pre[not(@data-learning-code)]'):
        check(bool(''.join(pre.itertext()).strip()),str(f)+': empty prompt')
        if pre.get('data-mode'):check(pre.get('data-mode') in ['text','image','video','audio'],str(f)+': mode')
        prompts+=1
for g in GUIDES:
    d=docs[KB/g['file']];check(len(d.xpath('//article//*[contains(@class,"human-example")]'))==3,g['file']+': three worked examples')
    check(len(d.xpath('//article//pre'))==6,g['file']+': three requests and follow-ups')
    check(len(d.xpath('//article/ol/li'))<=5,g['file']+': small action sequence')
    for c in g['cases']:
        check(len(c['prompt'])>70,g['file']+': complete brief')
        check(all(c[k].strip() for k in ['result','why','followup']),g['file']+': complete explanation')
for file,count in [('004.html',62),('005.html',41)]:
    cards=docs[KB/file].xpath('//details[contains(@class,"catalog-item")]');check(len(cards)==count,file+': profile count')
    for card in cards:
        check(len(card.xpath('.//*[contains(@class,"human-example")]'))==3,card.get('id')+': examples')
        check(len(card.xpath('.//pre'))==6,card.get('id')+': copyable prompts')
        check(bool(card.xpath('./div/h2[text()="Где открыть"]')),card.get('id')+': user path')
check(len(ROLE_LESSONS)==41,'41 original role explanations')
# Preserved practical IDs and original prompts remain usable.
for n in range(1,10):
    menu=docs[KB/f'module-{n:02d}.html'];check(len(menu.xpath('//ol[contains(@class,"task-menu")]/li'))==3,'business module '+str(n))
    for j in range(1,4):
        f=f'module-{n:02d}-{j}.html';d=docs[KB/f]
        check(len(d.xpath('//form[contains(@class,"short-quiz")]'))==1,f+': quiz preserved')
        check(len(d.xpath('//*[@data-job-done]'))==1,f+': progress preserved')
        old=subprocess.run(['git','show','HEAD:outputs/knowledge-base/'+f],cwd=ROOT,capture_output=True,text=True,check=True).stdout
        original=html.fromstring(old).xpath('//section[contains(@class,"query-block")]/pre')[0]
        current=d.xpath('//section[contains(@class,"query-block")]/pre')[0]
        check(''.join(original.itertext())==''.join(current.itertext()),f+': complete original request')
check(bool(docs[KB/'program.html'].xpath('//*[@data-learning-portable]')),'portable business progress remains available')
check('Печать' not in ''.join(docs[KB/'index.html'].xpath('//header')[0].itertext()),'no print in static header')
rows=json.loads((ROOT/'work/cms-publication/prod-full.json').read_text())
plans=publish_kb.build_plan(rows,{})
routes=json.loads((ROOT/'scripts/kb-routes.json').read_text())
for g in GUIDES:
    blocks=plans[routes['pages'][g['file']]]['blocks']
    q=[b for b in blocks if b['__component']=='kb.prompt']
    check(len(q)==6,g['file']+': CMS preserves every request')
    for i,c in enumerate(g['cases']):
        check(q[2*i]['prompt']==c['prompt'] and q[2*i]['mode']==c['mode'],g['file']+': CMS request/tool match')
        check(q[2*i+1]['mode']==c.get('followup_mode',c['mode']),g['file']+': CMS follow-up tool')
check(plans['index']['blocks'][0]['url']==publish_kb.url(routes['pages']['003.html']),'native home opens first chat')
check(plans['nachalo-raboty']['order']<plans['uchebnye-moduli']['order'],'native start precedes business modules')
for s in plans:
    for b in plans[s]['blocks']:
        if b['__component']=='kb.prompt':check(b['prompt'].strip(),s+': native empty request')
report=dict(status='failed' if errors else 'passed',html_checked=len(docs),kb_content_pages=articles,
            authored_guides=len(GUIDES),model_profiles=62,role_profiles=41,native_pages=len(plans),
            native_prompts=sum(b['__component']=='kb.prompt' for p in plans.values() for b in p['blocks']),errors=errors)
(ROOT/'work/human-kb/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(bool(errors))

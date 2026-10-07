#!/usr/bin/env python3
"""Build the human user-guide layer over the existing static knowledge base.

Preserves old addresses, catalog anchors, quizzes and browser progress IDs.
No network, account actions or generation calls. Re-running is idempotent.
"""
from pathlib import Path
import copy, hashlib, html, json, re
from lxml import html as LH
from user_guide_content import GUIDES, ROLE_LESSONS, ROLE_RESULTS, TEXT_RESULTS, MODEL_FAMILIES, SUPPLEMENTS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/knowledge-base'
WORK=ROOT/'work/human-kb'
E=lambda x:html.escape(str(x),quote=True)
BY_FILE={g['file']:g for g in GUIDES}
VERSION=hashlib.sha256((Path(__file__).read_bytes()+Path(__file__).with_name('user_guide_content.py').read_bytes()+(OUT/'revision.js').read_bytes())).hexdigest()[:12]
CAT_DATA=Path(__file__).with_name('user-guide-catalog.json')

def fragment(s):return LH.fragment_fromstring(s)
def p(s):return '<p>'+E(s)+'</p>'
def a(href,label):return '<a class="button" href="'+E(href)+'">'+E(label)+'</a>'
def query(s,id,mode='text'):return '<pre id="'+E(id)+'" data-mode="'+E(mode)+'">'+E(s)+'</pre><button type="button" class="primary copy-button" data-copy="'+E(id)+'">Копировать запрос</button>'
def screenshot(file,caption):
    assert (ROOT/'outputs/assets'/file).is_file(),file
    return '<figure class="module-screen"><img loading="lazy" src="../assets/'+E(file)+'" alt="'+E(caption)+'"><figcaption>'+E(caption)+'</figcaption><button type="button" class="image-expand" data-preview>Увеличить изображение</button></figure>'
def saved_media(file,caption):
    src=file if file.startswith('../') else '../assets/'+file
    assert (OUT/src).resolve().is_file(),src
    ext=Path(src).suffix
    if ext=='.mp4':inner='<video controls preload="metadata" playsinline aria-label="'+E(caption)+'"><source src="'+E(src)+'" type="video/mp4"></video>'
    elif ext in ('.mp3','.wav'):inner='<audio controls preload="metadata" aria-label="'+E(caption)+'"><source src="'+E(src)+'"></audio>'
    else:inner='<img loading="lazy" src="'+E(src)+'" alt="'+E(caption)+'">'
    return '<figure class="module-screen">'+inner+'<figcaption>'+E(caption)+'</figcaption></figure>'

def worked(c,id,number,fold=False):
    title='Пример '+str(number)+'. '+c['title']
    start='<details class="human-example"><summary>'+E(title)+'</summary>' if fold else '<section class="human-example"><h2>'+E(title)+'</h2>'
    mode=c.get('mode','text')
    tool={'text':'Текст','image':'Фото','video':'Видео','audio':'Аудио'}[mode]
    followup_mode=c.get('followup_mode',mode)
    next_tool={'text':'Текст','image':'Фото','video':'Видео','audio':'Аудио'}[followup_mode]
    next_label='Следующий шаг в «'+next_tool+'»' if followup_mode!=mode else 'Следующий вариант описания' if mode=='audio' else 'Следующее сообщение'
    return start+p('Для этого примера откройте «'+tool+'».')+'<h3>Запрос для этого примера</h3>'+query(c['prompt'],id,mode)+'<div class="human-result"><h3>Как может выглядеть результат</h3>'+p(c['result'])+'</div><h3>Что здесь полезно</h3>'+p(c['why'])+'<h3>'+E(next_label)+'</h3>'+query(c['followup'],id+'-edit',followup_mode)+('</details>' if fold else '</section>')

def article_body(g):
    s='<article class="kb-article human-guide" data-page="'+g['file']+'"><h1>'+E(g['title'])+'</h1><p class="lead">'+E(g['intro'])+'</p>'
    s+='<h2>Как это работает</h2>'+''.join(p(x) for x in g['explain'])
    if g['terms']:s+='<details><summary>Два слова, которые пригодятся</summary>'+''.join('<p><strong>'+E(k)+':</strong> '+E(v)+'</p>' for k,v in g['terms'])+'</details>'
    s+='<h2>Попробуйте по шагам</h2><ol class="action-steps">'+''.join('<li>'+E(x)+'</li>' for x in g['steps'])+'</ol>'+a('https://moleculai.ru/dashboard','Открыть Молекулу')
    if g['screen']:s+=screenshot(*g['screen'])
    s+='<p class="example-origin">Ниже учебные образцы. Ваш результат может отличаться; сохранённые генерации подписаны отдельно.</p>'
    for i,c in enumerate(g['cases'],1):s+=worked(c,g['file'].removesuffix('.html')+'-case-'+str(i),i,fold=i>1)
    for file,caption in g['media']:s+=saved_media(file,caption)
    s+='<details class="human-trouble"><summary>Если результат не подходит</summary>'+''.join(p(x) for x in g['errors'])+'</details>'
    s+='<h2>Попробуйте со своей задачей</h2><p>Выберите один пример, замените исходные сведения своими и сохраните удачную версию. Сравните первый ответ с результатом одной правки.</p><div class="actions">'+''.join(a(h,l) for h,l in g['next_links'])+'</div></article>'
    result=fragment(s)
    if g['file']=='008.html':result.xpath('./h2')[0].set('id','video-prices')
    return result

SECTIONS=[
('С чего начать','start.svg',['003.html','choose-model.html','010.html','019.html','trends-guide.html','008.html','help-common.html']),
('Текст и языковые модели','text.png',['text-life.html','text-study.html','text-resume.html','text-translation.html','text-business.html','text-presentation.html','021-karusel.html','021.html','021-plan.html','022.html','017.html','025.html','026.html','027.html']),
('Изображения','image.png',['image-first.html','photo-styles.html','042.html','image-marketplace.html','041.html','043.html','image-series.html','046.html','040.html','044.html','045.html','048.html']),
('Видео','video.png',['video-first.html','video-templates.html','051.html','video-story.html','059.html','060.html','065.html','067.html','068.html']),
('Аватары','avatar.svg',['avatar-guide.html','043-pasport.html','066.html']),
('Аудио','audio.png',['072.html','audio-lyrics.html','074.html','075.html','073.html']),
('Роли','roles.svg',['005-start.html','005.html']),
('Проекты и файлы','folder.png',['006.html','007.html','009.html']),
]

def all_titles(docs):return {f:''.join(d.xpath('//article/h1')[0].itertext()) for f,d in docs.items() if d.xpath('//article/h1')}

def nav(current,titles,models,roles):
    # Use only observed, existing design assets; SVG filenames vary in the older theme.
    def icon(name):
        path=ROOT/'outputs/assets/figma-ui'/name
        return '<img class="nav-icon" src="../assets/figma-ui/'+E(name)+'" alt="">' if path.exists() else ''
    def navlink(file,title):return '<a href="'+E(file)+'"'+(' aria-current="page"' if current==file else '')+'>'+E(title)+'</a>'
    s='<aside id="learning-menu" class="sidebar kb-sidebar"><a class="kb-brand" href="index.html" aria-label="Молекула: база знаний"><img class="brand-symbol" src="../assets/figma-ui/logo-symbol.png" alt=""><img class="brand-wordmark" src="../assets/figma-ui/logo-wordmark.png" alt="Молекула"></a><button class="nav-close" aria-label="Закрыть меню">×</button><nav class="kb-quick-nav" aria-label="Быстрые переходы">'+navlink('index.html','База знаний')+navlink('003.html','Первый чат')+'</nav><nav class="kb-tree" aria-label="Оглавление">'
    for label,ico,files in SECTIONS:
        active=current in files or (current=='004.html' and label=='Текст и языковые модели')
        s+='<details class="kb-tree-branch"'+(' open' if active else '')+'><summary><span class="tree-chevron">›</span>'+icon(ico)+E(label)+'</summary><div class="kb-tree-children">'
        for f in files:
            if f in titles:s+=navlink(f,titles[f])
        kind={'Текст и языковые модели':'Текст','Изображения':'Картинки','Видео':'Видео','Аудио':'Аудио'}.get(label)
        if kind:
            s+='<details class="kb-tree-branch"><summary><span class="tree-chevron">›</span>Модели</summary><div class="kb-tree-children">'
            for m in models:
                if m['category']==kind:s+=navlink('004.html#catalog-'+m['id'], 'Молли 1.0' if m['id']=='text-molecula' else m['name'])
            s+='</div></details>'
        if label=='Роли':
            for cat in ['Соцсети','Тексты','Продажи','Аналитика','Работа','Про себя']:
                s+='<details class="kb-tree-branch"><summary><span class="tree-chevron">›</span>'+E(cat)+'</summary><div class="kb-tree-children">'
                for r in roles:
                    if r['category']==cat:s+=navlink('005.html#catalog-'+r['id'],r['name'])
                s+='</div></details>'
        s+='</div></details>'
    s+='<details class="kb-tree-branch"'+(' open' if current.startswith('module-') or current=='program.html' else '')+'><summary><span class="tree-chevron">›</span>'+icon('modules.svg')+'Практика для бизнеса</summary><div class="kb-tree-children">'+navlink('program.html','Выбрать практическую задачу')
    for n in range(1,10):
        f=f'module-{n:02d}.html';s+='<details class="kb-tree-branch"'+(' open' if current.startswith(f'module-{n:02d}') else '')+'><summary><span class="tree-chevron">›</span>'+E(titles[f])+'</summary><div class="kb-tree-children">'+navlink(f,'Обзор')
        for j in range(1,4):
            f=f'module-{n:02d}-{j}.html';s+=navlink(f,titles[f])
        s+='</div></details>'
    s+='</div></details>'+navlink('reference.html','Все инструкции')+'</nav><nav class="platform-nav" aria-label="Молекула"><a href="https://moleculai.ru/">Главный сайт ↗</a><a href="https://moleculai.ru/chat">ИИ-чат ↗</a><a href="https://moleculai.ru/tools">Инструменты ↗</a><a href="https://moleculai.ru/dashboard">Открыть кабинет ↗</a></nav></aside>'
    return fragment(s)

def directory_article(title,intro,items):
    return fragment('<article class="kb-article human-guide"><h1>'+E(title)+'</h1><p class="lead">'+E(intro)+'</p><div class="directory-grid">'+''.join('<a class="directory-card" href="'+E(f)+'"><h2>'+E(t)+'</h2><p>'+E(note)+'</p></a>' for f,t,note in items)+'</div></article>')

def home():
    first='<article class="kb-article human-guide"><h1>Как пользоваться Молекулой</h1><p class="lead">Письма, учёба, работа, изображения, видео и музыка. Начните с одной понятной задачи.</p><section class="first-step"><h2>Первый чат</h2><p>Напишите короткое сообщение, получите ответ и попробуйте одну правку. Пример уже заполнен, свои файлы не нужны.</p><a class="button primary" href="003.html">Попробовать первый чат</a></section><h2>Выберите, что хотите сделать</h2><div class="directory-grid">'
    cards=[('text-life.html','Написать сообщение','Письмо, приглашение, бытовой план.'),('text-study.html','Разобраться в теме','Объяснение и вопросы для проверки себя.'),('text-resume.html','Подготовить резюме','Реальный опыт и тренировка интервью.'),('image-first.html','Создать изображение','Сцена, свет и композиция.'),('image-marketplace.html','Сделать карточки товара','Реальное фото, свойства и подписи.'),('video-first.html','Оживить фотографию','Один кадр и одно движение.'),('072.html','Создать музыку','Описание, стиль и вокал.'),('text-presentation.html','Подготовить презентацию','Содержание слайдов и речь к ним.')]
    first+=''.join('<a class="directory-card" href="'+f+'"><h2>'+t+'</h2><p>'+note+'</p></a>' for f,t,note in cards)
    first+='</div><h2>Как устроено обучение</h2><p>В руководстве сначала объясняется инструмент, затем показаны действия и три примера с полными запросами. Начните с первого, остальные открывайте по необходимости. После каждой пробы уточните одно расхождение.</p><div class="actions">'+a('choose-model.html','Выбрать модель')+a('005-start.html','Выбрать роль')+a('006.html','Собрать проект')+a('program.html','Практика для бизнеса')+a('reference.html','Все инструкции')+'</div></article>'
    return fragment(first)

def model_case(p):
    category=p['category'];id=p['id']
    if id.startswith('text-model-'):result=TEXT_RESULTS[int(id.rsplit('-',1)[1])-1]
    elif id=='text-molecula':result=TEXT_RESULTS[0]
    elif category=='Картинки':result='Ожидается изображение: '+p['description']+' Сравните его с исходником. '+p['check']
    elif category=='Видео':result='Ожидается короткий план: '+p['description']+' '+p['check']
    else:result='Ожидается музыкальный вариант для прослушивания. '+p['check']
    return dict(title=p['task'],prompt=p['prompt'],result=result,
                why='В этом примере важны конкретные исходные сведения: '+p['input'],
                followup=('Сохрани главный предмет и ракурс. Сделай фон спокойнее, без новых объектов.' if category=='Картинки' else 'Сделай движение камеры спокойнее. Сохрани исходный объект, свет и действие.' if category=='Видео' else 'Сделай следующую версию короче и проще, сохрани исходные сведения.' if category=='Текст' else 'Сделай музыкальную фактуру проще, сохрани настроение и отсутствие вокала.'))

def model_examples(m,index):
    category=m['category'];id=m['id'];first=model_case(m)
    if category=='Текст':
        refs=['003.html','text-life.html','text-study.html','text-resume.html','text-translation.html','text-presentation.html','010.html','007.html']
        g=BY_FILE[refs[index%len(refs)]];examples=[copy.deepcopy(g['cases'][index%3]),copy.deepcopy(BY_FILE[refs[(index+3)%len(refs)]]['cases'][(index+1)%3])]
    elif category=='Картинки':
        ref='042.html' if 'editor' in id or 'nb-pro' in id or 'sunburst' in id else '041.html' if 'ideogram' in id else 'image-first.html' if 'midjourney' in id or 'flux' in id or 'grok' in id else 'photo-styles.html'
        examples=[copy.deepcopy(BY_FILE[ref]['cases'][0]),copy.deepcopy(BY_FILE[ref]['cases'][2])]
    elif category=='Видео':examples=[copy.deepcopy(BY_FILE['video-first.html']['cases'][1]),copy.deepcopy(BY_FILE['051.html']['cases'][0])]
    else:
        examples=[copy.deepcopy(BY_FILE['072.html']['cases'][1]),dict(title='Спокойный трек для самостоятельного слушания',prompt='Инструментальная ambient-композиция для тихого вечера. Мягкий синтезатор, редкие ноты фортепиано, медленное развитие, плавные переходы. Без вокала, ударных и резкого финала. Музыка спокойная, с ощущением пространства.',result='Ожидается отдельный спокойный трек без слов. Прослушайте переходы и окончание: они должны поддерживать выбранное настроение.',why='Назначение отличается от рекламной подложки: здесь музыку слушают самостоятельно. Темп и фактура описаны явно.',followup='Спокойная инструментальная ambient-композиция для тихого вечера. Только мягкий синтезатор и редкие ноты фортепиано, ещё меньше событий, плавное развитие. Без вокала, ударных и резкого окончания.',mode='audio')]
    cases=[first]+examples
    first['mode']={'Текст':'text','Картинки':'image','Видео':'video','Аудио':'audio'}[category]
    if category=='Аудио':first['followup']=BY_FILE['072.html']['cases'][0]['followup']
    return cases

def enrich_models(doc,models):
    # Remove the older ultra-short introduction; keep filter and catalog elements intact.
    old=doc.xpath('//section[contains(@class,"model-family-guide")]')
    if old:old[0].getparent().replace(old[0],fragment('<section class="model-family-guide"><h2>Сначала выберите инструмент</h2><p>В карточке модели есть объяснение, входные материалы и три примера. Сначала выберите нужный результат, затем откройте один подходящий пункт. Это учебные сценарии, а не сравнительный тест скорости или качества всех версий.</p><div class="actions">'+a('choose-model.html','Как выбирать')+a('image-first.html','Первое изображение')+a('video-first.html','Первое видео')+a('072.html','Первая музыка')+'</div></section>'))
    doc.xpath('//article/h1')[0].text='Модели Молекулы: возможности и примеры'
    for i,m in enumerate(models):
        id='catalog-'+m['id'];el=doc.get_element_by_id(id)
        name='Молли 1.0' if m['id']=='text-molecula' else m['name']
        if m['id']=='text-molecula':el.xpath('./summary//strong')[0].text=name
        family=next((value for key,value in sorted(MODEL_FAMILIES.items(),key=lambda kv:-len(kv[0])) if name.startswith(key)),None)
        if m['id']=='text-molecula':family='Универсальный помощник Молекулы из списка текстовых моделей. Задачу можно описать обычными словами; для первого опыта начните с текста.'
        assert family,name
        intro=name+'. '+family
        mode={'Текст':'Текст','Картинки':'Фото','Видео':'Видео','Аудио':'Аудио'}[m['category']]
        output={'Текст':'Ответ в чате: письмо, объяснение, таблица или план.','Картинки':'Изображение для проверки и сохранения.','Видео':'Короткий клип, который нужно просмотреть целиком.','Аудио':'Музыкальный трек для прослушивания.'}[m['category']]
        s='<div class="catalog-body human-catalog"><p>'+E(intro)+'</p><h2>Что получится</h2>'+p(output)+'<h2>Где открыть</h2>'+p('Кабинет → «'+mode+'» → выбор модели под полем → '+name+'.')+'<h2>Что подготовить</h2>'+p(m['input'])
        if m['category']=='Картинки':s+=p('Опишите объект, расположение и свет. Для конкретного товара приложите фото. Для правки отдельно назовите изменяемое и сохраняемое.')
        elif m['category']=='Видео':s+=p('После выбора откройте «Настройки чата». Длительность, формат, звук и входные материалы могут отличаться у версий. Проверьте доступные поля и цену, затем опишите одно движение.')
        elif m['category']=='Аудио':s+=p('В «Авто» заполните описание. В «Детальном» слова песни и музыкальный стиль вводятся отдельно. Для инструментального варианта выберите «Без вокала».')
        else:s+=p('Задайте адресата и длину ответа. После первой версии можно попросить конкретную правку в том же разговоре.')
        s+=p('Образцы ниже подготовлены для обучения. Фактический ответ выбранной версии может отличаться; оцените его по своей задаче.')
        for n,c in enumerate(model_examples(m,i),1):s+=worked(c,id+'-example-'+str(n),n,fold=n>1)
        s+='<details><summary>Как понять, что пример удался</summary>'+p(m['check'])+p('Если есть расхождение, назовите его в следующем сообщении. Сравнивайте одну правку за раз.')+'</details><div class="actions">'+a('https://moleculai.ru/dashboard','Открыть кабинет')+a('choose-model.html','Как сравнить две модели')+'</div></div>'
        oldbody=el.xpath('./div[contains(@class,"catalog-body")]')[0];oldbody.getparent().replace(oldbody,fragment(s))

def role_case(spec,number):
    title,prompt,result=spec
    return dict(title=title,prompt=prompt,result=result,
                why='Роль получила конкретную ситуацию и форму результата. Сравните ответ с исходными сведениями, затем выберите фрагмент для правки.',
                followup='Сделай ответ проще для человека, который впервые читает этот материал. Исходные числа, условия и порядок сохрани.')

def enrich_roles(doc,roles):
    old=doc.xpath('//section[contains(@class,"role-task-guide")]')
    if old:old[0].getparent().replace(old[0],fragment('<section class="role-task-guide"><h2>Помощник под вашу задачу</h2><p>Роль задаёт способ работы, а исходные сведения передаёте вы. В каждой карточке объясняется назначение и показаны три примера. Можно работать и без роли.</p>'+a('005-start.html','Как открыть чат с ролью')+'</section>'))
    doc.xpath('//article/h1')[0].text='Роли Молекулы: что поручить и какой ответ ждать'
    for role in roles:
        n=int(role['id'].rsplit('-',1)[1]);desc,second,third=ROLE_LESSONS[n];id='catalog-'+role['id']
        el=doc.get_element_by_id(id);oldbody=el.xpath('./div[contains(@class,"catalog-body")]')[0]
        if role.get('prompt'):
            first=dict(title=role.get('document') or 'Первый пример',prompt=re.sub(r'Факт \d+: ','',role['prompt']),result=ROLE_RESULTS[n],why='Ситуация и исходные сведения заданы в запросе. Проверьте, сохранил ли ответ эти условия и помог ли человеку сделать следующий шаг.',followup='Подготовь чистовую версию без комментариев редактора. Сохрани исходные сведения.')
        else:
            # Previously hidden personal roles now get human-readable, non-predictive exercises.
            third_extras={12:('Три идеи заметки','Придумай три заголовка творческой заметки «Семь маленьких радостей». Объясни замысел каждого до одного предложения. Это игра с числом, без прогнозов.', 'Три варианта заголовка для обычной творческой рубрики.'),13:('Звёздная иллюстрация','Помоги описать иллюстрацию вымышленного наблюдателя звёзд: герой у окна с блокнотом, тихий вечер. Дай визуальный запрос без текста и без прогноза событий.', 'Описание художественной сцены, пригодное для дальнейшей работы в «Фото». '),30:('Маленькая проба','Для вымышленного персонажа напиши сцену: он хочет начать рисовать и делает маленькую пробу на открытке. До 80 слов, покажи действие вместо определения типа личности.', 'Короткая художественная сцена с наблюдаемым действием.'),32:('Единицы в записи','В учебной записи написано «йогурт 100 ккал, порция 150 г». Объясни, чего не хватает для расчёта: значение относится к 100 г или всей упаковке? Дай один уточняющий вопрос. Не назначай диету.', 'Уточняющий вопрос о том, к какой массе относится указанная энергия.')}
            first=role_case(third_extras[n],1)
        s='<div class="catalog-body human-catalog"><p>'+E(desc)+'</p><h2>Где открыть</h2>'+p('Кабинет → «Роли» → «'+role['name']+'» → «Начать чат с ролью». Выбор роли также есть рядом с полем сообщения.')+'<h2>Что передать</h2>'+p('Опишите ситуацию, вставьте исходные сведения и скажите, что хотите получить. Выберите один пример ниже и замените его условия своими.')
        s+=p('Это учебные образцы возможных результатов. Роль не знает ваши обстоятельства, пока вы их не описали.')
        for i,c in enumerate([first,role_case(second,2),role_case(third,3)],1):s+=worked(c,id+'-example-'+str(i),i,fold=i>1)
        s+='<details><summary>Если ответ слишком общий</summary><p>Добавьте конкретный эпизод, исходный текст или число. Попросите один нужный результат вместо большого перечня советов.</p></details>'+a('https://moleculai.ru/dashboard/roles','Открыть роли')+'</div>'
        oldbody.getparent().replace(oldbody,fragment(s))
    for el in doc.xpath('//section[contains(@class,"personal-roles")]/h3'):el.text='Для себя и творческих задач'

ROLE_SUPPLEMENT={
'012.html':9,'013.html':10,'014.html':23,'017.html':5,'020.html':22,'021.html':7,
'021-plan.html':18,'022.html':16,'023.html':5,'024.html':37,'025.html':20,
'025-peredacha.html':20,'026.html':15,'026-zadanie.html':15,'026-adaptaciya.html':29,
'027.html':19,'027-dannye.html':19,'027-srednee.html':19,
}

def supplement(doc,file,guide_file=None,indices=(0,1),role_number=None):
    article=doc.xpath('//article')[0]
    # Remove earlier generated supplements before rebuilding.
    for el in article.xpath('./section[contains(@class,"human-supplement")]'):article.remove(el)
    ref=BY_FILE[guide_file or 'text-business.html']
    if role_number:
        desc,c2,c3=ROLE_LESSONS[role_number];examples=[role_case(c2,2),role_case(c3,3)];intro=desc
    else:examples=[copy.deepcopy(ref['cases'][i]) for i in indices];intro=ref['intro']
    if file=='040.html':
        examples=[dict(title='Знак для книжного клуба',prompt='Создай простой знак вымышленного книжного клуба: открытая книга и небольшой круг над ней, один синий цвет, светлый фон, без текста и сложных градиентов. Знак должен читаться маленьким.',result='Ожидается простой растровый эскиз. Он не является автоматически готовым векторным логотипом.',why='Простота помогает оценить идею до доработки фирменного знака.',followup='Убери мелкие детали внутри книги, сохрани силуэт и круг.'),dict(title='Идея названия и знака',prompt='Для вымышленной мастерской керамики предложи три идеи простого знака. Образ: спокойная работа руками, небольшие группы. Для каждой дай форму, один цвет и объяснение. Названия брендов и чужие логотипы не используй.',result='Три текстовые идеи, например миска, отпечаток или простая линия формы. Выбранную идею можно передать в «Фото».',why='Сначала выбирается смысл, затем визуальный эскиз.',followup='Выбери идею миски и подготовь короткий запрос для изображения без надписей.')]
    if file=='044.html':
        examples=[dict(title='Светлая мастерская',prompt='Концепция небольшой мастерской керамики: два рабочих стола, открытые полки, светлые стены, мягкий дневной свет, натуральное дерево. Широкий обзор с уровня глаз. Без людей и надписей. Это визуальная идея, не строительный проект.',result='Ожидается концептуальная сцена с двумя столами. Реальные размеры и конструктивные решения требуют отдельной работы.',why='Назначение и число столов помогают проверить сцену.',followup='Сохрани два стола и свет. Уменьши декоративные предметы на полках.'),dict(title='Тот же интерьер, другой свет',prompt='По приложенной концепции мастерской измени только освещение на мягкий вечерний свет. Сохрани число столов, полки и расположение мебели. Не добавляй новые стены, двери и окна.',result='Ожидается другая атмосфера в прежней планировке.',why='Одна переменная делает сравнение наглядным.',followup='Свет слишком жёлтый. Сделай его нейтральнее, мебель сохрани.')]
    s='<section class="human-supplement"><h2>Ещё два примера этого способа работы</h2>'+p(intro)+p('Образцы ниже подготовлены для обучения; это дополнительные ситуации, а не новые запуски модели.')
    for i,c in enumerate(examples,2):s+=worked(c,file.removesuffix('.html')+'-extra-'+str(i),i,fold=True)
    s+='<div class="actions">'+a(ref['file'],'Подробное руководство')+'</div></section>'
    # Extra worked examples precede the existing quiz and next-page links.
    stop=article.xpath('./section[contains(@class,"single-check")]|./nav[contains(@class,"page-nav")]|./div[contains(@class,"task-done")]')
    if stop:article.insert(article.index(stop[0]),fragment(s))
    else:article.append(fragment(s))

def main():
    WORK.mkdir(exist_ok=True,parents=True)
    docs={f.name:LH.parse(str(f)).getroot() for f in OUT.glob('*.html')}
    template=copy.deepcopy(docs['003.html'])
    catalogs=json.loads(CAT_DATA.read_text())
    models=catalogs['models'];roles=catalogs['roles']
    for g in GUIDES:
        doc=docs.get(g['file'])
        if doc is None or not doc.xpath('//article'):doc=copy.deepcopy(template)
        old=doc.xpath('//article')[0]
        old.getparent().replace(old,article_body(g));docs[g['file']]=doc
    old=docs['index.html'].xpath('//article')[0];old.getparent().replace(old,home())
    program=docs['program.html'].xpath('//article')[0]
    program.xpath('./h1')[0].text='Практика для бизнеса'
    if not program.xpath('./details[contains(@class,"portable-progress")]'):
        program.append(fragment('<details class="portable-progress" data-learning-portable><summary>Сохранить или восстановить отметки заданий</summary><p>В статической версии отметки сохраняются в этом браузере. Для переноса скопируйте код.</p><pre id="learning-progress-code" data-learning-code></pre><button data-copy="learning-progress-code">Копировать код</button><label for="learning-progress-import-text">Сохранённый код</label><input id="learning-progress-import-text" data-learning-import-code autocomplete="off"><button data-learning-import>Восстановить отметки</button><p data-learning-message role="status"></p></details>'))
    enrich_models(docs['004.html'],models);enrich_roles(docs['005.html'],roles)
    for f,(ref,indices) in SUPPLEMENTS.items():
        if f in BY_FILE:continue
        supplement(docs[f],f,ref,indices,ROLE_SUPPLEMENT.get(f))
    # Add matched examples to each of the 27 preserved business exercises.
    task_overrides={
        (4,3):('text-resume.html',(1,2),15),
        (8,2):('avatar-guide.html',(1,2),None),
        (8,3):('avatar-guide.html',(0,2),None),
        (9,2):('008.html',(0,2),28),
        (9,3):('text-business.html',(1,2),23),
        (6,3):('text-presentation.html',(0,1),None),
    }
    for n in range(1,10):
        refs={1:'003.html',2:'text-business.html',3:'text-presentation.html',4:'007.html',5:'image-marketplace.html',6:'image-first.html',7:'video-first.html',8:'072.html',9:'image-marketplace.html'}
        for j in range(1,4):
            ref,indices,rn=task_overrides.get((n,j),(refs[n],(j%3,(j+1)%3),None))
            supplement(docs[f'module-{n:02d}-{j}.html'],f'module-{n:02d}-{j}.html',ref,indices,rn)
    titles=all_titles(docs)
    # Keep the specialised articles reachable, while the primary tree starts with tools.
    items=[]
    ordered=[f for _,_,files in SECTIONS for f in files]+['004.html','005.html','program.html']
    ordered+=sorted(f for f in titles if f not in ordered and f not in ['index.html','reference.html'] and not f.startswith('module-'))
    for f in dict.fromkeys(ordered):
        if f in titles:
            intro=BY_FILE[f]['intro'] if f in BY_FILE else 'Дополнительная инструкция и разобранные примеры.'
            items.append((f,titles[f],intro))
    old=docs['reference.html'].xpath('//article')[0];old.getparent().replace(old,directory_article('Все инструкции','Выберите нужное действие. Для первой попытки откройте «Первый чат».',items))
    titles=all_titles(docs)
    index=[]
    for f,doc in docs.items():
        if not doc.xpath('//article'):continue # Legacy redirects retain their exact target.
        title=titles[f]
        doc.xpath('//title')[0].text=title+' · Молекула'
        for meta in doc.xpath('//meta[@name="description"]'):meta.set('content','Понятные инструкции Молекулы: действия в кабинете, полные запросы и примеры результатов.')
        old=doc.get_element_by_id('learning-menu');old.getparent().replace(old,nav(f,titles,models,roles))
        for label in doc.xpath('//span[contains(@class,"top-label")]'):label.text='База знаний'
        crumbs=doc.xpath('//div[contains(@class,"breadcrumbs")]')
        if crumbs:
            for el in crumbs[0].xpath('./span'):el.text='/ '+title
        for link in doc.xpath('//head/link[@rel="stylesheet"]'):
            if 'user-guide.css' not in link.get('href',''):link.set('href',link.get('href').split('?')[0]+'?v='+VERSION)
        for el in doc.xpath('//script[@src]'):el.set('src',el.get('src').split('?')[0]+'?v='+VERSION)
        existing=doc.xpath('//head/link[starts-with(@href,"user-guide.css")]')
        if not existing:doc.xpath('//head')[0].append(fragment('<link rel="stylesheet" href="user-guide.css?v='+VERSION+'">'))
        else:existing[0].set('href','user-guide.css?v='+VERSION)
        # Public archive files are retained; interactive progress IDs remain unchanged.
        (OUT/f).write_text('<!doctype html>\n'+LH.tostring(doc,encoding='unicode',method='html')+'\n')
        group=BY_FILE[f]['group'] if f in BY_FILE else 'Практика' if f.startswith('module-') else 'Инструкции'
        group={'nachalo-raboty':'Начало работы','prompty-i-kontekst':'Запросы и контекст',
               'redaktura-poisk-i-perevod':'Работа с текстом','proekty-i-materialy':'Проекты и файлы',
               'tekst-i-yazykovye-modeli':'Текст','dokumenty-i-komanda':'Документы и работа',
               'teksty-i-publikatsii':'Тексты и публикации','izobrazheniya':'Изображения',
               'pravki-i-proverka-kachestva':'Правки изображений','kartochki-i-tovarnye-foto':'Карточки товара',
               'brend-portrety-i-skhemy':'Портреты и схемы','video':'Видео',
               'stsenarij-dvizhenie-i-semka':'Движение и сценарий','avatary':'Аватары',
               'audio':'Аудио','muzyka-i-zvukovye-effekty':'Музыка',
               'golos-i-rasshifrovka':'Голосовой ввод','roli-dlya-biznesa':'Роли'}.get(group,group)
        article=doc.xpath('//article')[0]
        keywords=' '.join(article.itertext())[:12000]
        index.append(dict(title=title,type=group,href=f,keywords=keywords))
    for filename,data,kind in [('004.html',models,'Модель'),('005.html',roles,'Роль')]:
        for row in data:index.append(dict(title='Молли 1.0' if row['id']=='text-molecula' else row['name'],type=kind,href=filename+'#catalog-'+row['id'],keywords=row.get('task','')+' '+row.get('description','')))
    (OUT/'search-index.js').write_text('window.SEARCH_INDEX='+json.dumps(index,ensure_ascii=False)+';\n')
    js=re.sub(r"x\.title\+' '\+x\.type(?:\+' '\+\(x\.keywords\|\|''\))*", "x.title+' '+x.type+' '+(x.keywords||'')",(OUT/'revision.js').read_text())
    (OUT/'revision.js').write_text(js)
    (OUT/'user-guide.css').write_text('''/* User-guide teaching layout, layered over the established Molecula theme. */
.human-guide .lead{max-width:760px}.human-guide>p{max-width:780px}.human-example{margin:28px 0;border:1px solid var(--line,#e9e9ee);border-radius:20px;padding:24px;background:#fff}.human-example>summary{font-size:18px;font-weight:600;cursor:pointer}.human-example h3{font-size:16px;margin:24px 0 12px}.human-example pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f7fa;border-radius:14px;padding:20px;font-size:15px;line-height:1.65}.human-result{background:#f5f3ff;border-radius:16px;padding:4px 20px 12px;margin-top:20px}.human-result h3{color:#6236bd}.human-catalog>h2{font-size:20px}.human-catalog .human-example{padding:18px}.example-origin{font-size:14px;color:#777}.human-trouble{margin-top:30px}.human-guide .action-steps li{margin-bottom:12px}.module-screen video,.module-screen audio{max-width:100%;width:100%}.kb-tree-children>a{line-height:1.4}.kb-tree-branch summary{align-items:flex-start}.human-supplement{margin-top:36px}.human-example .copy-button{margin-top:8px}@media(max-width:680px){.human-example{padding:16px;border-radius:16px}.human-example pre{padding:14px;font-size:14px}.human-result{padding:4px 14px 10px}.human-example>summary{font-size:16px}.human-catalog .human-example{padding:12px}}
''')
    meta={g['file']:{'parent':g['group'],'mode':'image' if g['file'] in ['image-first.html','photo-styles.html','042.html','041.html','043.html','image-series.html'] else 'video' if g['file'] in ['video-first.html','051.html','video-templates.html'] else 'audio' if g['file']=='072.html' else 'text'} for g in GUIDES}
    (ROOT/'scripts/user-guide-routes.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    report={'guides':len(GUIDES),'role_profiles':len(roles),'model_profiles':len(models),'extended_specialised_articles':len(SUPPLEMENTS),'preserved_practical_tasks':27,'new_generations':0}
    (WORK/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()

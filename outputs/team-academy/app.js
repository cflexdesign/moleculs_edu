document.documentElement.classList.add('js');
const esc = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const readProgress = () => { try { const p=JSON.parse(localStorage.getItem('molecula-team-lessons-v1')||'{}'); return p&&typeof p==='object' ? p : {}; } catch { return {}; } };
function updateProgress() {
  const p=readProgress(), keys=['development','marketing','hr','projects','ads','seo'];
  const total=keys.reduce((sum,k)=>sum+[1,2,3,4,5].filter(i=>p[k+'-'+i]).length,0);
  document.querySelectorAll('[data-team-total]').forEach(x=>x.textContent=total+' из 30');
}
document.querySelectorAll('[data-lesson]').forEach(x=>{
  x.checked=!!readProgress()[x.dataset.lesson];
  x.addEventListener('change',()=>{ const p=readProgress(); p[x.dataset.lesson]=x.checked;
    try { localStorage.setItem('molecula-team-lessons-v1',JSON.stringify(p)); } catch {} updateProgress();
  });
});
updateProgress();
const sidebar=document.querySelector('#kb-sidebar'), menu=document.querySelector('#menu-toggle'), backdrop=document.querySelector('#menu-backdrop');
function closeMenu(restoreFocus=false) {
  if(!sidebar||!menu||!backdrop)return;
  sidebar.classList.remove('open');menu.setAttribute('aria-expanded','false');backdrop.hidden=true;document.body.classList.remove('kb-menu-open');
  if(restoreFocus)menu.focus();
}
menu?.addEventListener('click',()=>{
  const open=!sidebar.classList.contains('open');sidebar.classList.toggle('open',open);menu.setAttribute('aria-expanded',String(open));backdrop.hidden=!open;document.body.classList.toggle('kb-menu-open',open);
  if(open) sidebar.querySelector('[data-nav-close]')?.focus();
});
document.querySelector('[data-nav-close]')?.addEventListener('click',()=>closeMenu(true));
backdrop?.addEventListener('click',()=>closeMenu(true));
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'){ if(sidebar?.classList.contains('open'))closeMenu(true); const results=document.querySelector('#search-results');if(results)results.hidden=true; }});
sidebar?.addEventListener('keydown',ev=>{
  if(ev.key!=='Tab'||!sidebar.classList.contains('open'))return;
  const items=Array.from(sidebar.querySelectorAll('a,button,input,summary')).filter(x=>!x.hidden&&x.getClientRects().length);
  const first=items[0], last=items[items.length-1];
  if(ev.shiftKey&&document.activeElement===first){ev.preventDefault();last?.focus();}
  else if(!ev.shiftKey&&document.activeElement===last){ev.preventDefault();first?.focus();}
});
document.querySelector('[data-collapse]')?.addEventListener('click',()=>document.querySelectorAll('.kb-tree details').forEach(x=>x.open=false));
const sideSearch=document.querySelector('#kb-side-search');
sideSearch?.addEventListener('input',()=>{
  const q=sideSearch.value.toLowerCase().trim();let n=0;
  document.querySelectorAll('.kb-tree-branch').forEach(d=>{
    const department=d.querySelector('summary')?.textContent.toLowerCase()||'', matchDepartment=department.includes(q);
    d.querySelectorAll('a').forEach(a=>{a.hidden=!(matchDepartment||a.textContent.toLowerCase().includes(q));if(!a.hidden)n++;});
    d.hidden=!Array.from(d.querySelectorAll('a')).some(a=>!a.hidden);if(q)d.open=!d.hidden;
  });
  document.querySelector('#side-empty').hidden=n!==0;
});
const search=document.querySelector('#global-search'), results=document.querySelector('#search-results');
search?.addEventListener('input',()=>{
  const q=search.value.toLowerCase().trim();results.hidden=!q;if(!q){results.innerHTML='';return;}
  const words=q.split(/\s+/), hits=(window.SALES_SEARCH||[]).filter(x=>words.every(w=>(x.title+' '+x.category+' '+x.text).toLowerCase().includes(w))).sort((a,b)=>Number(b.title.toLowerCase().includes(q))-Number(a.title.toLowerCase().includes(q)));
  results.innerHTML=hits.length?hits.slice(0,10).map(x=>'<a href="'+esc(x.url)+'">'+esc(x.title)+'<small>'+esc(x.category)+'</small></a>').join(''):'<p class="team-search-empty">Ничего не найдено</p>';
});
search?.addEventListener('focus',()=>{if(search.value.trim())results.hidden=false;});
search?.addEventListener('keydown',ev=>{if(ev.key==='ArrowDown'&&!results.hidden){const first=results.querySelector('a');if(first){ev.preventDefault();first.focus();}}});
document.addEventListener('click',ev=>{if(!ev.target.closest('.top-search')&&results)results.hidden=true;});
const library=document.querySelector('#library-search'), group=document.querySelector('#library-group');
function filterLibrary() {
  const q=library.value.toLowerCase().trim();let n=0;
  document.querySelectorAll('[data-library-card]').forEach(x=>{x.hidden=!(x.dataset.search.toLowerCase().includes(q)&&(!group.value||x.dataset.group===group.value));if(!x.hidden)n++;});
  document.querySelectorAll('[data-library-group]').forEach(s=>{s.hidden=!Array.from(s.querySelectorAll('[data-library-card]')).some(x=>!x.hidden);s.open=!!(q||group.value)&&!s.hidden;});
  document.querySelector('#library-count').textContent=n+' из 36 правил';document.querySelector('#library-empty').hidden=n!==0;
}
if(library&&group){library.addEventListener('input',filterLibrary);group.addEventListener('change',filterLibrary);}
let toastTimer;
function toast(text){const el=document.querySelector('#team-toast');if(!el)return;el.textContent=text;el.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.hidden=true,2200);}
async function copy(text) {
  if(navigator.clipboard&&window.isSecureContext){try{await navigator.clipboard.writeText(text);return;}catch{}}
  const area=document.createElement('textarea');area.value=text;area.className='team-copy-fallback';document.body.append(area);area.focus();area.select();const ok=document.execCommand('copy');area.remove();if(!ok)throw Error('copy');
}
document.querySelectorAll('[data-copy-query]').forEach(button=>button.addEventListener('click',async()=>{
  const text=button.closest('.team-query')?.querySelector('[data-query]')?.textContent;
  if(!text)return;
  try{await copy(text);button.focus();toast('Запрос скопирован');}catch{button.focus();toast('Выделите текст запроса и скопируйте вручную');}
}));
document.querySelector('[data-print]')?.addEventListener('click',()=>window.print());

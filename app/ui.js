'use strict';
const cells = ['network','endpoint','identity','server','hunting'];
let token = sessionStorage.getItem('silent-ridge-token'), generation = 0;
const el = id => document.getElementById(id);
function signedOut() {
  window.dispatchEvent(new Event('analysis-clear'));
  generation++; token = null; sessionStorage.removeItem('silent-ridge-token');
  el('workspace').hidden = true; el('login-panel').hidden = false;
  ['mission-content','guide-content','dispatch-content','manifests'].forEach(id=>el(id).replaceChildren());
  el('control-events').replaceChildren();
  el('tickets').replaceChildren(); el('files').replaceChildren(); el('body').value = '';
  document.title = 'Sign in · Silent Ridge';
}
function signedIn(cell) {
  el('login-panel').hidden = true; el('workspace').hidden = false;
  el('session-label').textContent = `Signed in as ${cell} · this tab only`;
  el('ticket').value = String(cells.indexOf(cell)+1); el('status').value = '';
  el('message').textContent = ''; document.title = `${cell} · Silent Ridge`;
}
async function api(path, payload) {
  const current = token, headers = {Authorization: `Bearer ${current || ''}`};
  if (payload !== undefined) Object.assign(headers, {'Content-Type':'application/json','X-Exercise-Request':'1'});
  const response = await fetch(path, {credentials:'omit', headers, method:payload === undefined ? 'GET':'POST', body:payload === undefined ? undefined:JSON.stringify(payload)});
  if (response.status === 401 && token === current) signedOut();
  if (!response.ok) { const result = await response.json(); throw new Error(result.error || 'Request failed'); }
  return response;
}
function failure(error) { el(token ? 'message':'login-error').textContent = error.message; }
async function download(file) {
  const response = await api('/files/'+file.split('/').map(encodeURIComponent).join('/'));
  const url = URL.createObjectURL(await response.blob()), a = document.createElement('a');
  a.href = url; a.download = file.split('/').pop(); document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url),1000);
}
// Render only text and structural Markdown; source HTML is never executed.
function renderDocument(text) {
  const root=document.createElement('div');root.className='document';
  const lines=text.replace(/\r/g,'').split('\n');
  let paragraph=[];
  const add=(tag,value,parent=root)=>{const n=document.createElement(tag);n.textContent=value;parent.append(n);return n;};
  const flush=()=>{if(paragraph.length){add('p',paragraph.join(' '));paragraph=[];}};
  for(let i=0;i<lines.length;i++){
    const line=lines[i];
    if(line.startsWith('```')){
      flush();const code=[];while(++i<lines.length&&!lines[i].startsWith('```'))code.push(lines[i]);
      add('pre',code.join('\n'));continue;
    }
    if(line.startsWith('|')){
      flush();const wrap=add('div','');wrap.className='table-scroll';const table=add('table','',wrap);
      let header=true;
      while(i<lines.length&&lines[i].startsWith('|')){
        const row=lines[i++].split('|').slice(1,-1).map(x=>x.trim());
        if(row.every(x=>/^:?-+:?$/.test(x)))continue;
        const tr=add('tr','',table);row.forEach(x=>add(header?'th':'td',x,tr));header=false;
      }i--;continue;
    }
    const heading=line.match(/^(#{1,6}) (.*)/);
    if(heading){flush();add('h'+Math.min(heading[1].length+1,6),heading[2]);}
    else if(!line.trim())flush();
    else paragraph.push(line);
  }
  flush();return root;
}
const guideNames={
 'handouts/cells.md':'Cell assignments',
 'common/collection.md':'Collection context and scope',
 'common/schedule.md':'Exercise schedule and deadlines',
 'handouts/worksheets.md':'Reporting templates'
};
function isNarrative(file){return file==='handouts/handover.md'||Object.hasOwn(guideNames,file)||/^inject-\d+\/command\.md$/.test(file);}
async function refresh() {
  const epoch = generation;
  const [files,tickets,control] = await Promise.all([api('/api/files').then(r=>r.json()),api('/api/tickets').then(r=>r.json()),api('/api/control').then(r=>r.json())]);
  if (epoch !== generation || !token) return;
  const narratives=await Promise.all(files.filter(isNarrative).map(async file=>[file,await (await api('/files/'+file)).text()]));
  if(epoch!==generation||!token)return;
  window.dispatchEvent(new CustomEvent('evidence-files',{detail:files.filter(f=>!isNarrative(f)&&!f.endsWith('SHA256SUMS.json'))}));
  ['files','manifests','mission-content','guide-content','dispatch-content'].forEach(id=>el(id).replaceChildren());
  files.filter(file=>!isNarrative(file)).forEach(file => {
    const li=document.createElement('li'),button=document.createElement('button');
    button.textContent=file;button.className='file-link';
    button.addEventListener('click',()=>download(file).catch(failure));li.append(button);
    el(file.endsWith('SHA256SUMS.json')?'manifests':'files').append(li);
  });
  narratives.sort(([a],[b])=>Object.keys(guideNames).indexOf(a)-Object.keys(guideNames).indexOf(b)).forEach(([file,text])=>{
    const content=renderDocument(text);
    if(file==='handouts/handover.md')el('mission-content').append(content);
    else if(Object.hasOwn(guideNames,file)){
      const detail=document.createElement('details'),summary=document.createElement('summary');
      detail.open=true;summary.textContent=guideNames[file];detail.append(summary,content);el('guide-content').append(detail);
    }else el('dispatch-content').append(content);
  });
  el('dispatches').hidden=!narratives.some(([file])=>file.endsWith('/command.md'));
  const node=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
  const elapsed=value=>value==null?'not started':(value/60).toFixed(2)+' min';
  const latest=control.at(-1);
  const clockEvent=control.filter(e=>['start','pause','resume'].includes(e.kind)).at(-1);
  el('clock-summary').textContent=latest?.elapsed_seconds!=null ? elapsed(latest.elapsed_seconds)+(clockEvent?.kind==='pause'?'  /  paused':'') : 'Not started';
  const release=control.filter(e=>e.kind==='release').at(-1);
  el('release-summary').textContent=release?'Inject '+release.details.inject:'Initial evidence';
  el('file-count').textContent=files.filter(f=>!isNarrative(f)&&!f.endsWith('SHA256SUMS.json')).length+' evidence artifacts';
  const comments=tickets.flatMap(t=>t.comments);
  el('activity-summary').textContent=comments.length+' team updates';
  el('refresh-time').textContent='Refreshed '+new Date().toLocaleTimeString();
  el('control-events').replaceChildren();
  if(!control.length) el('control-events').append(node('p','No controller records yet. Exercise control will start the clock and record decisions here.','empty'));
  [...control].reverse().forEach(event=>{
    const card=node('article','','ledger-event');
    card.append(node('h3',event.id+'  /  '+event.kind));
    card.append(node('p',event.actual_utc+'  /  elapsed '+elapsed(event.elapsed_seconds)+'  /  '+event.operator,'comment-meta'));
    const d=event.details;
    card.append(node('p',Object.entries(d).map(([key,value])=>key.replaceAll('_',' ')+': '+value).join('\n')));
    el('control-events').append(card);
  });
  el('tickets').replaceChildren();
  tickets.forEach(ticket=>{
    const article=node('article','','ticket-card');article.dataset.cell=ticket.owner;
    const heading=node('div','','ticket-heading');
    heading.append(node('h3','T'+ticket.id+'  /  '+ticket.owner),node('span',ticket.status,'badge'));article.append(heading);
    if(!ticket.comments.length) article.append(node('p','No updates yet. Share your initial findings and cite the evidence.','empty'));
    ticket.comments.forEach(comment=>{
      const block=node('div','','comment');
      block.append(node('div','T'+ticket.id+'-C'+comment.id+'  /  '+comment.author+'  /  '+comment.created+'  /  elapsed '+elapsed(comment.elapsed_seconds)+'  /  clock '+(comment.clock_event||'none'),'comment-meta'));
      block.append(node('p',comment.body,'comment-body'));article.append(block);
    });el('tickets').append(article);
  });
}
for (const id of ['cell-tabs','more-tabs']) cells.forEach(cell=> { const a=document.createElement('a'); a.href='/?cell='+cell; a.target='_blank'; a.rel='noopener noreferrer'; a.textContent=`Open ${cell} tab`; el(id).append(a); });
const selected=new URLSearchParams(location.search).get('cell');
if (cells.includes(selected)) el('login-cell').value=selected;
el('login').addEventListener('submit',async event=> {
  event.preventDefault(); el('sign-in').disabled=true; el('login-error').textContent='';
  try { const response=await api('/api/login',{cell:el('login-cell').value,password:el('password').value}); const result=await response.json(); generation++; token=result.token; sessionStorage.setItem('silent-ridge-token',token); el('password').value=''; signedIn(result.cell); await refresh(); }
  catch(error) { failure(error); } finally { el('sign-in').disabled=false; }
});
el('sign-out').addEventListener('click',async()=> { const epoch=generation; try { await api('/api/logout',{}); } catch(error) { if(token) return failure(error); } if(generation===epoch) signedOut(); });
el('joint-link').addEventListener('click',()=>{el('ticket').value='5';el('status').value='';el('body').focus();});
el('refresh').addEventListener('click',()=>refresh().catch(failure));
el('update').addEventListener('submit',async event=> {
  event.preventDefault(); const epoch=generation;
  try { const payload={ticket:Number(el('ticket').value),body:el('body').value}; if(el('status').value) payload.status=el('status').value;
    await api('/api/update',payload); if(epoch!==generation) return; el('body').value=''; el('message').textContent='Update saved'; await refresh();
  } catch(error) { failure(error); }
});
if(token) api('/api/me').then(r=>r.json()).then(user=> { signedIn(user.cell); return refresh(); }).catch(failure);

'use strict';
const cells = ['network','endpoint','identity','server','hunting'];
let token = sessionStorage.getItem('silent-ridge-token'), generation = 0;
const el = id => document.getElementById(id);
function signedOut() {
  generation++; token = null; sessionStorage.removeItem('silent-ridge-token');
  el('workspace').hidden = true; el('login-panel').hidden = false;
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
async function refresh() {
  const epoch = generation;
  const [files,tickets,control] = await Promise.all([api('/api/files').then(r=>r.json()),api('/api/tickets').then(r=>r.json()),api('/api/control').then(r=>r.json())]);
  if (epoch !== generation || !token) return;
  el('files').replaceChildren();
  files.forEach(file => { const li=document.createElement('li'), button=document.createElement('button'); button.textContent=file; button.className='file-link'; button.addEventListener('click',()=>download(file).catch(failure)); li.append(button); el('files').append(li); });
  el('control-events').replaceChildren();
  control.forEach(event => { const p=document.createElement('p'); p.textContent=`${event.id} · ${event.actual_utc} · elapsed ${event.elapsed_seconds == null ? 'not started' : (event.elapsed_seconds/60).toFixed(2)+' min'} · ${event.operator} (${event.host_user}) · ${event.kind}\n${JSON.stringify(event.details)}`; el('control-events').append(p); });
  el('tickets').replaceChildren();
  tickets.forEach(ticket => { const article=document.createElement('article'), h=document.createElement('h3'); h.textContent=`${ticket.id} · ${ticket.owner} · ${ticket.status}`; article.append(h); ticket.comments.forEach(comment=> { const p=document.createElement('p'); p.textContent=`T${ticket.id}-C${comment.id} · ${comment.created} · elapsed ${comment.elapsed_seconds == null ? 'not started / unavailable' : (comment.elapsed_seconds/60).toFixed(2)+' min'} · ${comment.author} · clock ${comment.clock_event || 'none'}\n${comment.body}`; article.append(p); }); el('tickets').append(article); });
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
el('refresh').addEventListener('click',()=>refresh().catch(failure));
el('update').addEventListener('submit',async event=> {
  event.preventDefault(); const epoch=generation;
  try { const payload={ticket:Number(el('ticket').value),body:el('body').value}; if(el('status').value) payload.status=el('status').value;
    await api('/api/update',payload); if(epoch!==generation) return; el('body').value=''; el('message').textContent='Update saved'; await refresh();
  } catch(error) { failure(error); }
});
if(token) api('/api/me').then(r=>r.json()).then(user=> { signedIn(user.cell); return refresh(); }).catch(failure);

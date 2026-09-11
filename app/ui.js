'use strict';
async function refresh() {
  const [filesResponse, ticketsResponse] = await Promise.all([fetch('/api/files'), fetch('/api/tickets')]);
  if (!filesResponse.ok || !ticketsResponse.ok) throw new Error('Unable to load. Check your cell login.');
  const files = await filesResponse.json(), tickets = await ticketsResponse.json();
  const list = document.querySelector('#files'); list.replaceChildren();
  files.forEach(file => { const li = document.createElement('li'), a = document.createElement('a'); a.textContent = file; a.href = '/files/' + file.split('/').map(encodeURIComponent).join('/'); li.append(a); list.append(li); });
  const board = document.querySelector('#tickets'); board.replaceChildren();
  tickets.forEach(ticket => { const article = document.createElement('article'), heading = document.createElement('h3'); heading.textContent = `${ticket.id} · ${ticket.owner} · ${ticket.status}`; article.append(heading); ticket.comments.forEach(comment => { const p = document.createElement('p'); p.textContent = `${comment.created} — ${comment.author}\n${comment.body}`; article.append(p); }); board.append(article); });
}
function failure(error) { document.querySelector('#message').textContent = error.message; }
document.querySelector('#refresh').addEventListener('click', () => refresh().catch(failure));
document.querySelector('#update').addEventListener('submit', async event => { event.preventDefault(); try { const payload = {ticket: Number(document.querySelector('#ticket').value), body: document.querySelector('#body').value}; const status = document.querySelector('#status').value; if (status) payload.status = status; const response = await fetch('/api/update', {method: 'POST', headers: {'Content-Type':'application/json','X-Exercise-Request':'1'}, body: JSON.stringify(payload)}); const result = await response.json(); if (!response.ok) throw new Error(result.error); document.querySelector('#body').value = ''; document.querySelector('#message').textContent = 'Update saved'; await refresh(); } catch(error) { failure(error); } });
refresh().catch(failure);

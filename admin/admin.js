'use strict';
const el=id=>document.getElementById(id);
let token=sessionStorage.getItem('silent-ridge-admin'),epoch=0;
function out(){epoch++;token=null;sessionStorage.removeItem('silent-ridge-admin');el('panel').hidden=true;el('login').hidden=false;for(const id of ['documents','tickets','ledger','credentials'])el(id).replaceChildren();for(const id of ['reason','reference','minute','decision','release-confirm','publish-confirm'])el(id).value='';}
async function api(path,payload){
 const response=await fetch(path,{method:payload===undefined?'GET':'POST',credentials:'omit',headers:{Authorization:'Bearer '+(token||''),'Content-Type':'application/json','X-Admin-Request':'1'},body:payload===undefined?undefined:JSON.stringify(payload)});
 const data=await response.json();if(response.status===401)out();if(!response.ok)throw Error(data.error);return data;
}
function message(e){el('message').textContent=e.message;}
function item(parent,title,text){const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('pre');s.textContent=title;p.textContent=text;d.append(s,p);parent.append(d);}
async function refresh(){
 const current=epoch,data=await api('/api/state');if(current!==epoch||!token)return;
 el('login').hidden=true;el('panel').hidden=false;el('identity').textContent='Signed in as '+data.user;
 for(const id of ['documents','tickets','ledger'])el(id).replaceChildren();
 Object.entries(data.documents).forEach(([name,text])=>item(el('documents'),name,text));
 data.tickets.forEach(t=>item(el('tickets'),'T'+t.id+' / '+t.owner+' / '+t.status+' / '+t.comments.length+' updates',t.comments.map(c=>'T'+t.id+'-C'+c[0]+' / '+c[1]+' / '+c[2]+'\n'+c[3]).join('\n\n')));
 [...data.events].reverse().forEach(e=>item(el('ledger'),e.id+' / '+e.kind+' / '+e.operator,JSON.stringify(e,null,2)));
}
async function action(payload){
 const buttons=[...document.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
 try{const data=await api('/api/action',payload);el('message').textContent=data.message;el('release-confirm').value='';el('publish-confirm').value='';await refresh();}
 catch(e){message(e);}finally{buttons.forEach(b=>b.disabled=false);}
}
el('login').onsubmit=async e=>{e.preventDefault();try{const data=await api('/api/login',{name:el('name').value,password:el('password').value});token=data.token;epoch++;sessionStorage.setItem('silent-ridge-admin',token);el('password').value='';el('message').textContent='';await refresh();}catch(e){message(e);}};
el('logout').onclick=async()=>{try{await api('/api/logout',{});}finally{out();}};
el('refresh').onclick=()=>refresh().catch(message);
for(const [kind,label] of [['start','Start clock'],['pause','Pause'],['resume','Resume'],['note','Save private note']]){
 const b=document.createElement('button');b.textContent=label;b.onclick=()=>action({action:kind,text:el('reason').value});el('controls').append(b);
}
el('release').onclick=()=>action({action:'release',number:Number(el('inject').value),confirm:el('release-confirm').value});
el('publish').onclick=()=>action({action:'decision',text:el('decision').value,request:el('reference').value,outcome:el('outcome').value,effective_minute:el('minute').value===''?null:Number(el('minute').value),confirm:el('publish-confirm').value});
el('export').onclick=()=>action({action:'export'});
el('logins').onclick=async()=>{const current=epoch;try{const data=await api('/api/logins');if(epoch===current&&token)el('credentials').textContent=data.logins;}catch(e){message(e);}};
el('hide-logins').onclick=()=>el('credentials').textContent='';
if(token)refresh().catch(message);

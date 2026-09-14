'use strict';
(()=>{
let result=null,descending=false,query='',request=0;
const get=id=>document.getElementById(id);
const make=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
const value=v=>v===null?'null':typeof v==='object'?JSON.stringify(v):String(v??'');
function clear(){request++;result=null;get('analysis-result').replaceChildren();get('artifact-meta').textContent='';get('sql-panel').hidden=true;get('sql-schema').textContent='';get('sql-query').value='';get('analysis-count').textContent='';get('analysis-message').textContent='';get('hash-result').textContent='';}
window.addEventListener('analysis-clear',()=>{clear();get('analysis-file').replaceChildren();});
window.addEventListener('evidence-files',event=>{
 const old=get('analysis-file').value;get('analysis-file').replaceChildren();
 event.detail.forEach(f=>{const option=make('option',f);option.value=f;get('analysis-file').append(option);});
 if(event.detail.includes(old))get('analysis-file').value=old;
 if(result&&!event.detail.includes(result.file))clear();
});
get('analysis-file').addEventListener('change',clear);
function cite(row,index){
 const id=row.id??row.packet;
 const reference=id!=null?'record '+value(id):query?'query result '+(index+1):'data row '+(index+1);
 const text='Evidence: '+result.file+' / '+reference+'\nSHA-256: '+result.sha256+
 (query?'\nSQL: '+query:'')+
 (get('analysis-filter').value?'\nViewer filter: '+get('analysis-filter').value:'')+
 '\nObserved record: '+JSON.stringify(row)+'\nAssessment: ';
 if(get('body').value.length+text.length+2>8000){get('analysis-message').textContent='This record is too large for the remaining draft space. Cite its source and record ID manually.';return;}
 get('body').value+=(get('body').value?'\n\n':'')+text;get('body').focus();get('composer').scrollIntoView();
}
function render(){
 if(!result)return;
 const filter=get('analysis-filter').value.toLowerCase(),column=get('analysis-sort').value;
 const rows=result.rows.map((row,index)=>({row,index})).filter(x=>Object.values(x.row).some(v=>value(v).toLowerCase().includes(filter)));
 if(column)rows.sort((a,b)=>value(a.row[column]).localeCompare(value(b.row[column]),undefined,{numeric:true})*(descending?-1:1));
 get('analysis-result').replaceChildren();
 get('analysis-count').textContent=rows.length+' matching records / '+result.rows.length+' loaded'+(result.truncated?' (limited to 1,000; narrow your SQL or download for further analysis)':'');
 if(result.text!==undefined){
  get('analysis-result').append(make('pre',result.text));
  const button=make('button','Cite this document');button.onclick=()=>cite({text:result.text.slice(0,1500)},0);get('analysis-result').append(button);
  get('analysis-count').textContent='Text artifact';return;
 }
 const table=make('table',''),head=make('tr','');
 head.append(make('th','Source reference'));result.columns.forEach(c=>head.append(make('th',c)));table.append(head);
 rows.forEach(({row,index})=>{
  const tr=make('tr',''),td=make('td',''),button=make('button','Cite '+value(row.id??row.packet??index+1));
  button.onclick=()=>cite(row,index);td.append(button);tr.append(td);result.columns.forEach(c=>tr.append(make('td',value(row[c]))));table.append(tr);
 });get('analysis-result').append(table);
}
async function open(sql=''){
 const ticket=++request,epoch=generation;
 get('analysis-message').textContent='Loading evidence...';
 try{
 const response=await api('/api/analyze',{file:get('analysis-file').value,query:sql});
 const data=await response.json();if(ticket!==request||epoch!==generation||!token)return;
 result=data;query=sql;get('analysis-message').textContent=data.notice||'Read-only evidence loaded.';
 get('artifact-meta').textContent=data.file+' / '+data.bytes+' bytes / SHA-256 '+data.sha256;
 get('sql-panel').hidden=!data.schema;
 get('sql-schema').textContent=(data.schema||[]).map(t=>t.sql).join('\n');
 get('analysis-sort').replaceChildren(make('option',''));
 data.columns.forEach(c=>get('analysis-sort').append(make('option',c)));
 get('analysis-filter').value='';get('hash-result').textContent='';render();
 }catch(error){if(ticket===request&&epoch===generation){result=null;get('analysis-result').replaceChildren();get('analysis-message').textContent=error.message;}}
}
get('analyze-open').onclick=()=>open();
get('sql-run').onclick=()=>open(get('sql-query').value);
get('analysis-filter').oninput=render;get('analysis-sort').onchange=render;
get('sort-direction').onclick=()=>{descending=!descending;get('sort-direction').textContent='Order: '+(descending?'descending':'ascending');render();};
get('hash-compare').oninput=()=>{
 const hash=get('hash-compare').value.trim().toLowerCase();
 get('hash-result').textContent=!result?'Open an artifact first.':!/^[0-9a-f]{64}$/.test(hash)?'Enter a 64-character SHA-256 digest.':hash===result.sha256?'Hashes match.':'Hashes differ.';
};
get('time-convert').onclick=()=>{
 const input=get('time-input').value.trim(),offset=Number(get('time-offset').value);
 const time=Date.parse(input);
 get('time-result').textContent=!/(Z|[+-]\d{2}:\d{2})$/i.test(input)||!Number.isFinite(time)||!Number.isFinite(offset)||Math.abs(offset)>86400?'Enter a timestamp with timezone and a correction within 24 hours.':new Date(time+offset*1000).toISOString();
};
})();

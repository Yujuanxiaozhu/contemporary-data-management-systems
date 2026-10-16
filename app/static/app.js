const $ = s => document.querySelector(s);
async function api(url, method='GET', data) {
  const response = await fetch(url, {method, headers: data ? {'Content-Type':'application/json'} : {}, body: data ? JSON.stringify(data) : undefined});
  if (response.status === 204) return null;
  const body = await response.json();
  if (!response.ok) { const error = new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)); error.status=response.status; throw error; }
  return body;
}
async function run(action) { try { await action(); $('#message').textContent='操作成功'; } catch(e) { $('#message').textContent=e.message; } }
function credentials() { return Object.fromEntries(new FormData($('#auth'))); }
async function refresh() {
  const user = await api('/api/auth/me'); $('#identity').textContent=`当前用户：${user.username}`;
  const surveys = await api('/api/surveys'); $('#list').replaceChildren();
  for (const survey of surveys) {
    const li=document.createElement('li'); const text=document.createElement('p');
    text.textContent=`${survey.title} · ${survey.status} · 预留链接 /survey/${survey.public_token}`; li.append(text);
    for (const [label, action] of [['发布','publish'],['关闭','close'],['删除','delete']]) {
      const button=document.createElement('button'); button.textContent=label;
      button.onclick=()=>run(async()=>{if(action==='delete' && !confirm('确认删除问卷？')) return; await api(`/api/surveys/${survey.id}${action==='delete'?'':'/'+action}`, action==='delete'?'DELETE':'POST'); await refresh();}); li.append(button);
    }
    $('#list').append(li);
  }
}
$('#auth').onsubmit=e=>{e.preventDefault(); run(async()=>{await api('/api/auth/login','POST',credentials()); $('#auth').password.value=''; await refresh();});};
$('#register').onclick=()=>run(async()=>{await api('/api/auth/register','POST',credentials());});
$('#logout').onclick=()=>run(async()=>{await api('/api/auth/logout','POST'); $('#identity').textContent='尚未登录'; $('#list').replaceChildren();});
$('#refresh').onclick=()=>run(refresh);
$('#survey').onsubmit=e=>{e.preventDefault(); run(async()=>{const form=$('#survey'); const d=Object.fromEntries(new FormData(form)); d.allow_anonymous=form.allow_anonymous.checked; d.allow_multiple_submissions=form.allow_multiple_submissions.checked; d.deadline=d.deadline?new Date(d.deadline).toISOString():null; await api('/api/surveys','POST',d); form.reset(); await refresh();});};
refresh().catch(error=>{if(error.status!==401) $('#message').textContent=error.message;});

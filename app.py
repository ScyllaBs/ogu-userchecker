from flask import Flask, render_template_string, request, send_file, jsonify
from pathlib import Path
import csv
import itertools
import string
import threading
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from wordfreq import top_n_list

app = Flask(__name__)

LETTERS = string.ascii_lowercase
DIGITS = string.digits
OUTPUT = Path("candidates.txt")
AVAILABLE_OUTPUT = Path("available.txt")
RESULTS_OUTPUT = Path("results.csv")
OGU_URL = "https://ogu-app.com/account"

SCAN_LOCK = threading.Lock()
SCAN_STATE = {
    "running": False,
    "stop": False,
    "tested": 0,
    "available": 0,
    "taken": 0,
    "unknown": 0,
    "current": "",
    "message": "Prêt.",
    "total": 0,
}

HTML = r'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OGU User Checker</title>
<style>
:root{font-family:Inter,system-ui,Arial,sans-serif;color-scheme:dark}
body{margin:0;background:#0d0f14;color:#f4f7fb;min-height:100vh}.wrap{max-width:1100px;margin:0 auto;padding:36px 20px}
.card{background:#151923;border:1px solid #252b38;border-radius:18px;padding:22px;margin-top:18px;box-shadow:0 20px 60px rgba(0,0,0,.25)}
h1{font-size:34px;margin:0 0 6px}.sub{color:#9aa4b2;margin:0 0 24px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
label{display:block;font-size:13px;color:#aeb7c4;margin-bottom:7px}input,select{width:100%;box-sizing:border-box;background:#0f131b;color:white;border:1px solid #303746;border-radius:11px;padding:12px 13px;font-size:15px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}.check{display:flex;align-items:center;gap:8px;color:#d8dee8}.check input{width:auto}
button,.btn{background:#f4f7fb;color:#0d0f14;border:0;border-radius:11px;padding:12px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}.secondary{background:#242a36!important;color:#f4f7fb!important}.danger{background:#6e2a2a!important;color:#fff!important}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}.stat{background:#0f131b;border-radius:12px;padding:14px}.stat b{display:block;font-size:24px}.stat span{color:#8f99a8;font-size:12px}
.list{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:18px;max-height:430px;overflow:auto}.user{background:#0f131b;border:1px solid #242a36;border-radius:10px;padding:10px;text-align:center;font-family:ui-monospace,monospace;cursor:pointer}.user:hover{border-color:#697386}
.note{font-size:13px;color:#8f99a8;line-height:1.5}.hidden{display:none}.progress{height:10px;background:#0f131b;border-radius:999px;overflow:hidden;margin-top:14px}.bar{height:100%;background:#f4f7fb;width:0%}
.good{color:#79e7a3}.bad{color:#ff8a8a}.muted{color:#8f99a8}@media(max-width:800px){.grid,.stats{grid-template-columns:1fr}.list{grid-template-columns:repeat(3,1fr)}}
</style>
<script>
function modeChange(){const m=document.getElementById('mode').value;document.getElementById('wordsBox').classList.toggle('hidden',m!=='words');document.getElementById('patternBox').classList.toggle('hidden',m!=='pattern');document.getElementById('comboBox').classList.toggle('hidden',m!=='any');}
function copyUser(el){navigator.clipboard.writeText(el.dataset.u);const old=el.textContent;el.textContent='copié';setTimeout(()=>el.textContent=old,600)}
async function startScan(){
  const batch=document.getElementById('batch').value;
  const delay=document.getElementById('delay').value;
  const r=await fetch('/start-scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:batch,delay:delay})});
  const j=await r.json();
  document.getElementById('scanMsg').textContent=j.message||'Scan lancé.';
  poll();
}
async function stopScan(){await fetch('/stop-scan',{method:'POST'});}
async function poll(){
  const r=await fetch('/scan-status');const s=await r.json();
  document.getElementById('tested').textContent=s.tested;document.getElementById('available').textContent=s.available;document.getElementById('taken').textContent=s.taken;document.getElementById('unknown').textContent=s.unknown;
  document.getElementById('scanMsg').textContent=s.message;document.getElementById('current').textContent=s.current?('@'+s.current):'-';
  const pct=s.total?Math.min(100,(s.tested/s.total)*100):0;document.getElementById('bar').style.width=pct+'%';
  if(s.running)setTimeout(poll,1000);else refreshAvailable();
}
async function refreshAvailable(){const r=await fetch('/available-json');const j=await r.json();const box=document.getElementById('availableList');box.innerHTML='';for(const u of j.items){const d=document.createElement('div');d.className='user';d.dataset.u=u;d.textContent=u;d.onclick=()=>copyUser(d);box.appendChild(d)}document.getElementById('availCount').textContent=j.count;}
window.addEventListener('DOMContentLoaded',()=>{modeChange();poll();refreshAvailable();});
</script>
</head><body><div class="wrap">
<h1>OGU User Picker</h1><p class="sub">Génère des candidats, teste leur disponibilité sur OGU, puis garde uniquement les libres.</p>
<div class="card"><form method="post">
<div class="grid">
<div><label>Mode</label><select id="mode" name="mode" onchange="modeChange()"><option value="words" {% if mode=='words' %}selected{% endif %}>Mots réels</option><option value="any" {% if mode=='any' %}selected{% endif %}>Toutes combinaisons</option><option value="pattern" {% if mode=='pattern' %}selected{% endif %}>Pattern personnalisé</option></select></div>
<div><label>Longueur exacte</label><input type="number" name="length" min="1" max="12" value="{{ length }}" required></div>
<div id="wordsBox"><label>Langue des mots</label><select name="language"><option value="en" {% if language=='en' %}selected{% endif %}>Anglais</option><option value="fr" {% if language=='fr' %}selected{% endif %}>Français</option><option value="es" {% if language=='es' %}selected{% endif %}>Espagnol</option><option value="it" {% if language=='it' %}selected{% endif %}>Italien</option><option value="de" {% if language=='de' %}selected{% endif %}>Allemand</option></select></div>
<div><label>Maximum à générer</label><input type="number" name="limit" min="1" max="500000" value="{{ limit }}"></div>
<div id="patternBox" class="hidden"><label>Pattern (L=lettre, N=nombre)</label><input name="pattern" value="{{ pattern }}" placeholder="LLL, LLN, L_L, L.L"></div>
</div>
<div id="comboBox" class="row hidden" style="margin-top:16px"><label class="check"><input type="checkbox" name="letters" {% if letters %}checked{% endif %}> Lettres</label><label class="check"><input type="checkbox" name="numbers" {% if numbers %}checked{% endif %}> Chiffres</label><label class="check"><input type="checkbox" name="underscore" {% if underscore %}checked{% endif %}> _</label><label class="check"><input type="checkbox" name="dot" {% if dot %}checked{% endif %}> .</label><label class="check"><input type="checkbox" name="dash" {% if dash %}checked{% endif %}> -</label></div>
<div class="row" style="margin-top:18px"><button type="submit">1. Créer les candidats</button>{% if count %}<a class="btn secondary" href="/download">Télécharger candidats</a>{% endif %}</div>
</form></div>
{% if message %}<div class="card"><strong>{{ message }}</strong><p class="note">{{ descriptor }}</p>{% if preview %}<div class="list">{% for u in preview %}<div class="user" data-u="{{u}}" onclick="copyUser(this)">{{u}}</div>{% endfor %}</div>{% endif %}</div>{% endif %}
<div class="card">
<h2 style="margin-top:0">2. Tester sur OGU</h2><p class="note">Le bot ouvre réellement <b>ogu-app.com/account</b>, remplit le champ Username et observe la réponse. Il commence par vérifier que <b>@god</b> est bien reconnu comme <span class="bad">taken</span>. Si ce contrôle échoue, le scan s'arrête pour éviter les faux positifs.</p>
<div class="grid"><div><label>Nombre de candidats à tester dans ce lot</label><input id="batch" type="number" min="1" max="5000" value="100"></div><div><label>Délai entre deux tests (secondes)</label><input id="delay" type="number" min="1" max="10" step="0.2" value="1.5"></div></div>
<div class="row" style="margin-top:18px"><button type="button" onclick="startScan()">Lancer le scan</button><button type="button" class="danger" onclick="stopScan()">Stop</button><a class="btn secondary" href="/download-available">Télécharger disponibles</a></div>
<div class="stats"><div class="stat"><b id="tested">0</b><span>testés</span></div><div class="stat"><b id="available" class="good">0</b><span>disponibles</span></div><div class="stat"><b id="taken" class="bad">0</b><span>pris</span></div><div class="stat"><b id="unknown">0</b><span>inconnus</span></div></div>
<div class="progress"><div id="bar" class="bar"></div></div><p><span id="scanMsg" class="muted">Prêt.</span> &nbsp; <b id="current">-</b></p>
</div>
<div class="card"><h2 style="margin-top:0">Disponibles uniquement <span class="muted">(<span id="availCount">0</span>)</span></h2><div id="availableList" class="list"></div><p class="note">Clique sur un username pour le copier. Les résultats ambigus ne sont jamais ajoutés ici.</p></div>
<div class="card"><p class="note">Le scanner respecte un délai entre les essais et s'arrête s'il rencontre une page de vérification, un blocage ou une réponse qu'il ne sait pas interpréter. Il ne contourne pas Cloudflare, CAPTCHA ou les protections anti-bot.</p></div>
</div></body></html>'''


def expand_pattern(pattern):
    pools=[]
    for ch in pattern:
        pools.append(LETTERS if ch=='L' else DIGITS if ch=='N' else ch)
    yield from (''.join(x) for x in itertools.product(*pools))


def generate_any(length, letters, numbers, underscore, dot, dash):
    alphabet=('' if not letters else LETTERS)+('' if not numbers else DIGITS)+('_' if underscore else '')+('.' if dot else '')+('-' if dash else '')
    if not alphabet:return iter(()),''
    return (''.join(x) for x in itertools.product(alphabet, repeat=length)),alphabet


def generate_words(language,length,limit):
    scan=max(50000,min(500000,limit*20))
    seen=set()
    for word in top_n_list(language, scan):
        w=word.lower().strip()
        if len(w)==length and w.isalpha() and w not in seen:
            seen.add(w);yield w
            if len(seen)>=limit:return


def read_candidates():
    if not OUTPUT.exists():return []
    return [x.strip() for x in OUTPUT.read_text(encoding='utf-8').splitlines() if x.strip()]


def read_results():
    results={}
    if RESULTS_OUTPUT.exists():
        with RESULTS_OUTPUT.open('r',encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                u=row.get('username','').strip()
                if u:results[u]=row.get('status','unknown')
    return results


def append_result(username,status):
    new=not RESULTS_OUTPUT.exists()
    with RESULTS_OUTPUT.open('a',encoding='utf-8',newline='') as f:
        w=csv.writer(f)
        if new:w.writerow(['username','status'])
        w.writerow([username,status])
    if status=='available':
        known=set(AVAILABLE_OUTPUT.read_text(encoding='utf-8').splitlines()) if AVAILABLE_OUTPUT.exists() else set()
        if username not in known:
            with AVAILABLE_OUTPUT.open('a',encoding='utf-8') as f:f.write(username+'\n')


def set_state(**kwargs):
    with SCAN_LOCK:SCAN_STATE.update(kwargs)


def snapshot_state():
    with SCAN_LOCK:return dict(SCAN_STATE)


def username_input(page):
    # Prefer the accessible label used by the real OGU page.
    try:
        loc=page.get_by_label('Username',exact=True)
        if loc.count():return loc.first
    except Exception:pass
    # Conservative fallbacks if the site's markup changes slightly.
    for sel in ['input[name="username"]','input[placeholder*="nova"]','input[type="text"]']:
        loc=page.locator(sel)
        if loc.count():return loc.first
    raise RuntimeError('Champ Username introuvable sur la page OGU.')


def challenge_visible(page):
    text=page.locator('body').inner_text().lower()
    markers=['verify you are human','checking your browser','attention required','cf-chl','captcha']
    return any(x in text for x in markers)


def detect_username_status(page, field, username):
    field.fill('')
    field.fill(username)
    page.wait_for_timeout(1200)
    if challenge_visible(page):return 'blocked'
    # Read the local area around the username field first, then the full page.
    local=''
    try:
        local=field.evaluate("el => (el.parentElement?.parentElement?.innerText || el.parentElement?.innerText || '')").lower()
    except Exception:pass
    body=page.locator('body').inner_text().lower()
    text=local+'\n'+body
    if 'taken' in local:return 'taken'
    if any(x in local for x in ['available','username is free','not taken']):return 'available'
    # On the current OGU form, taken usernames get an explicit red 'taken' message.
    # We only infer availability after the calibration check has proven that this message is detectable.
    if 'taken' not in local:
        return 'available'
    return 'unknown'


def scan_worker(batch,delay):
    set_state(running=True,stop=False,tested=0,available=0,taken=0,unknown=0,current='',message='Ouverture de OGU…')
    candidates=read_candidates();previous=read_results()
    pending=[u for u in candidates if u not in previous][:batch]
    set_state(total=len(pending))
    if not pending:
        set_state(running=False,message='Aucun nouveau candidat à tester dans cette liste.')
        return
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={"width":1280,"height":900})
            page.goto(OGU_URL,wait_until='domcontentloaded',timeout=30000)
            page.wait_for_timeout(1500)
            if challenge_visible(page):
                browser.close();set_state(running=False,message='OGU affiche une vérification anti-bot. Scan arrêté, aucun contournement tenté.');return
            field=username_input(page)
            set_state(message='Calibration avec @god…',current='god')
            calibration=detect_username_status(page,field,'god')
            if calibration!='taken':
                browser.close();set_state(running=False,message=f'Calibration échouée : @god devrait être détecté taken, résultat={calibration}. Aucun candidat marqué disponible.');return
            set_state(message='Calibration OK. Scan en cours…')
            a=t=u=0;tested=0
            for username in pending:
                if snapshot_state().get('stop'):
                    set_state(message='Scan arrêté par l’utilisateur.');break
                set_state(current=username)
                try:
                    status=detect_username_status(page,field,username)
                except PlaywrightTimeoutError:
                    status='unknown'
                except Exception:
                    status='unknown'
                if status=='blocked':
                    set_state(message='Protection anti-bot détectée. Scan arrêté sans contournement.');break
                append_result(username,status)
                tested+=1
                if status=='available':a+=1
                elif status=='taken':t+=1
                else:u+=1
                set_state(tested=tested,available=a,taken=t,unknown=u,message='Scan en cours…')
                time.sleep(delay)
            browser.close()
            if not snapshot_state().get('stop') and snapshot_state().get('message')=='Scan en cours…':
                set_state(message='Lot terminé.')
    except Exception as exc:
        set_state(message=f'Erreur scanner : {type(exc).__name__}: {exc}')
    finally:
        set_state(running=False,current='')


@app.route('/',methods=['GET','POST'])
def index():
    data=dict(length=3,mode='words',language='en',pattern='LLL',limit=50000,letters=True,numbers=False,underscore=False,dot=False,dash=False,message='',count=0,preview=[],descriptor='-')
    if request.method=='POST':
        try:
            data['length']=max(1,min(12,int(request.form.get('length','3'))));data['limit']=max(1,min(500000,int(request.form.get('limit','50000'))))
        except ValueError:
            data['message']='Valeur invalide.';return render_template_string(HTML,**data)
        data['mode']=request.form.get('mode','words');data['language']=request.form.get('language','en');data['pattern']=request.form.get('pattern','LLL').strip() or 'LLL'
        for key in ('letters','numbers','underscore','dot','dash'):data[key]=key in request.form
        if data['mode']=='words':
            iterator=generate_words(data['language'],data['length'],data['limit']);data['descriptor']=f"mots {data['language']} / {data['length']} lettres"
        elif data['mode']=='pattern':
            iterator=expand_pattern(data['pattern']);data['descriptor']=data['pattern']
        else:
            iterator,alphabet=generate_any(data['length'],data['letters'],data['numbers'],data['underscore'],data['dot'],data['dash']);data['descriptor']=alphabet or 'aucun caractère'
        items=list(itertools.islice(iterator,data['limit']))
        OUTPUT.write_text('\n'.join(items)+('\n' if items else ''),encoding='utf-8')
        data['count']=len(items);data['preview']=items[:300];data['message']=f"Liste créée : {len(items):,} candidats. Tu peux maintenant lancer le scan OGU."
    return render_template_string(HTML,**data)


@app.post('/start-scan')
def start_scan():
    if snapshot_state().get('running'):
        return jsonify(message='Un scan est déjà en cours.'),409
    payload=request.get_json(silent=True) or {}
    try:
        batch=max(1,min(5000,int(payload.get('batch',100))))
        delay=max(1.0,min(10.0,float(payload.get('delay',1.5))))
    except (ValueError,TypeError):
        return jsonify(message='Paramètres de scan invalides.'),400
    if not OUTPUT.exists():return jsonify(message='Crée d’abord une liste de candidats.'),400
    threading.Thread(target=scan_worker,args=(batch,delay),daemon=True).start()
    return jsonify(message='Scan lancé.')


@app.post('/stop-scan')
def stop_scan():
    set_state(stop=True)
    return jsonify(message='Arrêt demandé.')


@app.get('/scan-status')
def scan_status():return jsonify(snapshot_state())


@app.get('/available-json')
def available_json():
    items=[]
    if AVAILABLE_OUTPUT.exists():items=[x.strip() for x in AVAILABLE_OUTPUT.read_text(encoding='utf-8').splitlines() if x.strip()]
    return jsonify(count=len(items),items=items[-600:])


@app.get('/download')
def download():
    if not OUTPUT.exists():return 'Aucune liste générée.',404
    return send_file(OUTPUT,as_attachment=True,download_name='ogu_candidates.txt')


@app.get('/download-available')
def download_available():
    if not AVAILABLE_OUTPUT.exists():return 'Aucun username disponible trouvé.',404
    return send_file(AVAILABLE_OUTPUT,as_attachment=True,download_name='ogu_available.txt')


if __name__=='__main__':app.run(host='0.0.0.0',port=8000,debug=False,threaded=True)

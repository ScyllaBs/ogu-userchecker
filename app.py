from flask import Flask, render_template_string, request, send_file
from pathlib import Path
import itertools
import string

from wordfreq import top_n_list

app = Flask(__name__)

LETTERS = string.ascii_lowercase
DIGITS = string.digits
OUTPUT = Path("candidates.txt")

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
button,.btn{background:#f4f7fb;color:#0d0f14;border:0;border-radius:11px;padding:12px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}.secondary{background:#242a36!important;color:#f4f7fb!important}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}.stat{background:#0f131b;border-radius:12px;padding:14px}.stat b{display:block;font-size:24px}.stat span{color:#8f99a8;font-size:12px}
.list{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:18px;max-height:430px;overflow:auto}.user{background:#0f131b;border:1px solid #242a36;border-radius:10px;padding:10px;text-align:center;font-family:ui-monospace,monospace;cursor:pointer}.user:hover{border-color:#697386}
.note{font-size:13px;color:#8f99a8;line-height:1.5}.hidden{display:none}@media(max-width:800px){.grid,.stats{grid-template-columns:1fr}.list{grid-template-columns:repeat(3,1fr)}}
</style>
<script>
function modeChange(){const m=document.getElementById('mode').value;document.getElementById('wordsBox').classList.toggle('hidden',m!=='words');document.getElementById('patternBox').classList.toggle('hidden',m!=='pattern');document.getElementById('comboBox').classList.toggle('hidden',m!=='any');}
function copyUser(el){navigator.clipboard.writeText(el.textContent.trim());el.textContent='copié';setTimeout(()=>el.textContent=el.dataset.u,600)}
window.addEventListener('DOMContentLoaded',modeChange)
</script>
</head><body><div class="wrap">
<h1>OGU User Picker</h1><p class="sub">Crée une liste de mots ou de combinaisons, puis pioche les usernames que tu préfères.</p>
<div class="card"><form method="post">
<div class="grid">
<div><label>Mode</label><select id="mode" name="mode" onchange="modeChange()"><option value="words" {% if mode=='words' %}selected{% endif %}>Mots réels</option><option value="any" {% if mode=='any' %}selected{% endif %}>Toutes combinaisons</option><option value="pattern" {% if mode=='pattern' %}selected{% endif %}>Pattern personnalisé</option></select></div>
<div><label>Longueur exacte</label><input type="number" name="length" min="1" max="12" value="{{ length }}" required></div>
<div id="wordsBox"><label>Langue des mots</label><select name="language"><option value="en" {% if language=='en' %}selected{% endif %}>Anglais</option><option value="fr" {% if language=='fr' %}selected{% endif %}>Français</option><option value="es" {% if language=='es' %}selected{% endif %}>Espagnol</option><option value="it" {% if language=='it' %}selected{% endif %}>Italien</option><option value="de" {% if language=='de' %}selected{% endif %}>Allemand</option></select></div>
<div><label>Maximum à afficher / sauvegarder</label><input type="number" name="limit" min="1" max="500000" value="{{ limit }}"></div>
<div id="patternBox" class="hidden"><label>Pattern (L=lettre, N=nombre)</label><input name="pattern" value="{{ pattern }}" placeholder="LLL, LLN, L_L, L.L"></div>
</div>
<div id="comboBox" class="row hidden" style="margin-top:16px"><label class="check"><input type="checkbox" name="letters" {% if letters %}checked{% endif %}> Lettres</label><label class="check"><input type="checkbox" name="numbers" {% if numbers %}checked{% endif %}> Chiffres</label><label class="check"><input type="checkbox" name="underscore" {% if underscore %}checked{% endif %}> _</label><label class="check"><input type="checkbox" name="dot" {% if dot %}checked{% endif %}> .</label><label class="check"><input type="checkbox" name="dash" {% if dash %}checked{% endif %}> -</label></div>
<div class="row" style="margin-top:18px"><button type="submit">Créer la liste</button>{% if count %}<a class="btn secondary" href="/download">Télécharger la liste</a>{% endif %}</div>
</form></div>
{% if message %}<div class="card"><strong>{{ message }}</strong><div class="stats"><div class="stat"><b>{{ count }}</b><span>résultats</span></div><div class="stat"><b>{{ shown }}</b><span>affichés</span></div><div class="stat"><b>{{ descriptor }}</b><span>sélection</span></div></div>
{% if preview %}<div class="list">{% for u in preview %}<div class="user" data-u="{{u}}" onclick="copyUser(this)">{{u}}</div>{% endfor %}</div><p class="note">Clique sur un username pour le copier. Le fichier téléchargé contient toute la liste générée, jusqu'à la limite choisie.</p>{% endif %}</div>{% endif %}
<div class="card"><p class="note"><b>Exemples :</b> 3 lettres + combinaisons = aaa, aab, aac… ; pattern LLN = aa0, aa1… ; mots réels + 5 lettres + anglais = liste de mots anglais de 5 lettres. “Tous les mots” signifie ici les mots connus de la base linguistique utilisée : aucun dictionnaire ne peut garantir absolument tous les mots existants.</p></div>
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
    # Pull a broad frequency-ranked vocabulary, then keep clean alphabetic words of exact length.
    scan=max(50000,min(500000,limit*20))
    seen=set()
    for word in top_n_list(language, scan):
        w=word.lower().strip()
        if len(w)==length and w.isalpha() and w not in seen:
            seen.add(w)
            yield w
            if len(seen)>=limit:return


@app.route('/',methods=['GET','POST'])
def index():
    data=dict(length=3,mode='words',language='en',pattern='LLL',limit=50000,letters=True,numbers=False,underscore=False,dot=False,dash=False,message='',count=0,preview=[],shown=0,descriptor='-')
    if request.method=='POST':
        try:
            data['length']=max(1,min(12,int(request.form.get('length','3'))));data['limit']=max(1,min(500000,int(request.form.get('limit','50000'))))
        except ValueError:
            data['message']='Valeur invalide.';return render_template_string(HTML,**data)
        data['mode']=request.form.get('mode','words');data['language']=request.form.get('language','en');data['pattern']=request.form.get('pattern','LLL').strip() or 'LLL'
        for key in ('letters','numbers','underscore','dot','dash'):data[key]=key in request.form
        if data['mode']=='words':
            iterator=generate_words(data['language'],data['length'],data['limit']);data['descriptor']=f"mots {data['language']} / {data['length']}L"
        elif data['mode']=='pattern':
            iterator=expand_pattern(data['pattern']);data['descriptor']=data['pattern']
        else:
            iterator,alphabet=generate_any(data['length'],data['letters'],data['numbers'],data['underscore'],data['dot'],data['dash']);data['descriptor']=alphabet or 'aucun caractère'
        items=list(itertools.islice(iterator,data['limit']))
        OUTPUT.write_text('\n'.join(items)+('\n' if items else ''),encoding='utf-8')
        data['count']=len(items);data['preview']=items[:600];data['shown']=len(data['preview']);data['message']=f"Liste créée : {len(items):,} usernames."
    return render_template_string(HTML,**data)

@app.get('/download')
def download():
    if not OUTPUT.exists():return 'Aucune liste générée.',404
    return send_file(OUTPUT,as_attachment=True,download_name='ogu_candidates.txt')

if __name__=='__main__':app.run(host='0.0.0.0',port=8000,debug=False)

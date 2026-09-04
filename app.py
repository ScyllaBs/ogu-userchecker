from flask import Flask, render_template_string, request, send_file
from pathlib import Path
import itertools
import string

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
body{margin:0;background:#0d0f14;color:#f4f7fb;min-height:100vh}
.wrap{max-width:980px;margin:0 auto;padding:42px 20px}
.card{background:#151923;border:1px solid #252b38;border-radius:18px;padding:22px;margin-top:18px;box-shadow:0 20px 60px rgba(0,0,0,.25)}
h1{font-size:34px;margin:0 0 6px}.sub{color:#9aa4b2;margin:0 0 24px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
label{display:block;font-size:13px;color:#aeb7c4;margin-bottom:7px}
input,select{width:100%;box-sizing:border-box;background:#0f131b;color:white;border:1px solid #303746;border-radius:11px;padding:12px 13px;font-size:15px}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.check{display:flex;align-items:center;gap:8px;color:#d8dee8}.check input{width:auto}
button,.btn{background:#f4f7fb;color:#0d0f14;border:0;border-radius:11px;padding:12px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}
button.secondary,.btn.secondary{background:#242a36;color:#f4f7fb}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}.stat{background:#0f131b;border-radius:12px;padding:14px}.stat b{display:block;font-size:24px}.stat span{color:#8f99a8;font-size:12px}
pre{background:#0f131b;border-radius:12px;padding:14px;max-height:280px;overflow:auto;white-space:pre-wrap;color:#cbd5e1}
.note{font-size:13px;color:#8f99a8;line-height:1.5}
@media(max-width:700px){.grid,.stats{grid-template-columns:1fr}}
</style>
</head>
<body><div class="wrap">
<h1>OGU User Checker</h1>
<p class="sub">Génère rapidement des usernames selon tes règles.</p>
<div class="card">
<form method="post">
<div class="grid">
<div><label>Longueur</label><input type="number" name="length" min="1" max="8" value="{{ length }}" required></div>
<div><label>Mode</label><select name="mode"><option value="any" {% if mode=='any' %}selected{% endif %}>Toutes combinaisons</option><option value="pattern" {% if mode=='pattern' %}selected{% endif %}>Pattern personnalisé</option></select></div>
<div><label>Pattern (L=lettre, N=nombre)</label><input name="pattern" value="{{ pattern }}" placeholder="LLL, LLN, L_L, L.L"></div>
<div><label>Limite de génération</label><input type="number" name="limit" min="1" max="500000" value="{{ limit }}"></div>
</div>
<div class="row" style="margin-top:16px">
<label class="check"><input type="checkbox" name="letters" {% if letters %}checked{% endif %}> Lettres</label>
<label class="check"><input type="checkbox" name="numbers" {% if numbers %}checked{% endif %}> Chiffres</label>
<label class="check"><input type="checkbox" name="underscore" {% if underscore %}checked{% endif %}> _</label>
<label class="check"><input type="checkbox" name="dot" {% if dot %}checked{% endif %}> .</label>
<label class="check"><input type="checkbox" name="dash" {% if dash %}checked{% endif %}> -</label>
</div>
<div class="row" style="margin-top:18px"><button type="submit">Générer</button>{% if count %}<a class="btn secondary" href="/download">Télécharger candidates.txt</a>{% endif %}</div>
</form>
</div>
{% if message %}<div class="card"><strong>{{ message }}</strong>
<div class="stats"><div class="stat"><b>{{ count }}</b><span>candidats</span></div><div class="stat"><b>{{ preview|length }}</b><span>aperçu</span></div><div class="stat"><b>{{ pattern_used }}</b><span>pattern / alphabet</span></div></div>
{% if preview %}<pre>{{ preview|join('\n') }}</pre>{% endif %}</div>{% endif %}
<div class="card"><p class="note">La génération fonctionne localement. La vérification réelle de disponibilité sur OGU n’est pas activée tant qu’une méthode d’accès autorisée n’est pas configurée. L’app ne contourne pas de CAPTCHA, anti-bot ou limite de requêtes.</p></div>
</div></body></html>'''


def expand_pattern(pattern):
    pools=[]
    for ch in pattern:
        if ch == 'L': pools.append(LETTERS)
        elif ch == 'N': pools.append(DIGITS)
        else: pools.append(ch)
    yield from (''.join(x) for x in itertools.product(*pools))


def generate_any(length, letters, numbers, underscore, dot, dash):
    alphabet=''
    if letters: alphabet += LETTERS
    if numbers: alphabet += DIGITS
    if underscore: alphabet += '_'
    if dot: alphabet += '.'
    if dash: alphabet += '-'
    if not alphabet:
        return iter(()), ''
    return (''.join(x) for x in itertools.product(alphabet, repeat=length)), alphabet


@app.route('/', methods=['GET','POST'])
def index():
    data=dict(length=3, mode='any', pattern='LLL', limit=50000, letters=True, numbers=False, underscore=False, dot=False, dash=False, message='', count=0, preview=[], pattern_used='-')
    if request.method == 'POST':
        try:
            data['length']=max(1,min(8,int(request.form.get('length','3'))))
            data['limit']=max(1,min(500000,int(request.form.get('limit','50000'))))
        except ValueError:
            data['message']='Valeur invalide.'
            return render_template_string(HTML, **data)
        data['mode']=request.form.get('mode','any')
        data['pattern']=request.form.get('pattern','LLL').strip() or 'LLL'
        for key in ('letters','numbers','underscore','dot','dash'):
            data[key]=key in request.form

        if data['mode']=='pattern':
            iterator=expand_pattern(data['pattern'])
            data['pattern_used']=data['pattern']
        else:
            iterator, alphabet=generate_any(data['length'], data['letters'], data['numbers'], data['underscore'], data['dot'], data['dash'])
            data['pattern_used']=alphabet or 'aucun caractère'

        items=list(itertools.islice(iterator, data['limit']))
        OUTPUT.write_text('\n'.join(items) + ('\n' if items else ''), encoding='utf-8')
        data['count']=len(items)
        data['preview']=items[:100]
        data['message']=f"Génération terminée : {len(items):,} usernames enregistrés."
    return render_template_string(HTML, **data)


@app.get('/download')
def download():
    if not OUTPUT.exists():
        return 'Aucun fichier généré.', 404
    return send_file(OUTPUT, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)

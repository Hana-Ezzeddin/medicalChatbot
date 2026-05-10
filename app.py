from flask import Flask, request, jsonify, render_template_string
import pandas as pd
import re

app = Flask(__name__)

# =========================
# LOAD KNOWLEDGE BASE
# =========================
def load_knowledge_base(csv_path):
    df = pd.read_csv(csv_path)
    df["precautions"] = df["precautions"].fillna("Consult a doctor")
    kb = {}
    for _, row in df.iterrows():
        disease = row["disease"].strip()
        symptoms = {s.strip() for s in row["symptoms"].split(",")}
        precautions = [p.strip() for p in row["precautions"].split(",")]
        if disease not in kb:
            kb[disease] = {"symptoms": set(), "precautions": precautions}
        kb[disease]["symptoms"].update(symptoms)
    return kb

kb = load_knowledge_base("Medical Diagnosis Expert System.csv")
all_symptoms = set()
for d in kb:
    all_symptoms.update(kb[d]["symptoms"])

# =========================
# NLP
# =========================
def preprocess(text):
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    return text.split()

def extract_symptoms(user_text):
    words = preprocess(user_text)
    phrase = " ".join(words)
    matched = set()
    for sym in all_symptoms:
        readable = sym.replace("_", " ")
        parts = readable.split()
        if readable in phrase or set(parts).issubset(words):
            matched.add(sym)
    return list(matched)

# =========================
# DIAGNOSIS LOGIC
# =========================
def diagnose(matched, denied):
    scores = []
    for disease, info in kb.items():
        disease_syms = info["symptoms"]
        common = set(matched).intersection(disease_syms)
        if common:
            confidence = len(common) / len(disease_syms)
            scores.append({
                "disease": disease,
                "confidence": confidence,
                "symptoms": disease_syms
            })
    if not scores:
        return {"type": "no_match"}
    scores.sort(key=lambda x: x["confidence"], reverse=True)
    if scores[0]["confidence"] < 0.6:
        return follow_up(scores, matched, denied)
    return final_result(scores)

def follow_up(scores, matched, denied):
    symptom_count = {}
    for d in scores:
        for s in d["symptoms"]:
            if s not in matched and s not in denied:
                symptom_count[s] = symptom_count.get(s, 0) + 1
    if not symptom_count:
        return final_result(scores)
    min_count = min(symptom_count.values())
    options = [s for s in symptom_count if symptom_count[s] == min_count][:5]
    return {
        "type": "options",
        "question": "Do you also experience any of these symptoms?",
        "options": options
    }

def final_result(scores):
    top = scores[:3]
    precautions = kb[top[0]["disease"]]["precautions"]
    return {
        "type": "result",
        "diseases": [
            {"name": r["disease"], "confidence": round(r["confidence"] * 100, 1)}
            for r in top
        ],
        "precautions": [p for p in precautions if p]
    }

# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    data    = request.json
    message = data.get("message", "")
    matched = data.get("matched", [])   # existing symptoms carried from frontend
    denied  = data.get("denied",  [])   # already-asked symptoms carried from frontend
    choice  = data.get("choice")
    accumulate = data.get("accumulate", False)  # merge vs. fresh-start flag

    if message:
        new_syms = extract_symptoms(message)
        if accumulate and matched:
            # ── FIX 1: merge new symptoms with existing ones mid-session ──
            matched = list(set(matched) | set(new_syms))
        else:
            # fresh start (first message, or post-result)
            matched = new_syms
            denied  = []

    elif choice:
        # ── FIX 2: choice carries full matched+denied state from frontend ──
        if choice not in matched:
            matched.append(choice)
        # denied already contains unchosen siblings (sent by frontend)

    if not matched:
        return jsonify({
            "response": {"type": "no_symptoms"},
            "matched": [], "denied": [], "detected": []
        })

    response = diagnose(matched, denied)
    return jsonify({
        "response": response,
        "matched":  matched,
        "denied":   denied,
        "detected": matched
    })

# =========================
# FRONTEND
# =========================
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anti · Medical AI</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=Figtree:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:     #05080f;
  --bg1:    #0a0d17;
  --bg2:    #111520;
  --g:      rgba(255,255,255,0.035);
  --b:      rgba(255,255,255,0.07);
  --b2:     rgba(255,255,255,0.12);
  --txt:    #d8e0f0;
  --muted:  #52637a;
  --cyan:   #00e8cc;
  --blue:   #4f8fff;
  --violet: #9b7fff;
  --green:  #2ddb96;
  --amber:  #f9a825;
  --r:      20px;
}

html, body { height:100%; overflow:hidden; }
body {
  background: var(--bg);
  color: var(--txt);
  font-family: 'Figtree', sans-serif;
  display: flex; align-items: center; justify-content: center;
}

#bg { position:fixed; inset:0; z-index:0; pointer-events:none; }

.orb { position:fixed; border-radius:50%; filter:blur(110px); pointer-events:none; z-index:0; }
.o1 { width:650px; height:650px; top:-18%; left:-12%;
      background:radial-gradient(circle,rgba(0,232,204,0.11),transparent 70%);
      animation:od1 30s ease-in-out infinite; }
.o2 { width:520px; height:520px; bottom:-12%; right:-8%;
      background:radial-gradient(circle,rgba(79,143,255,0.09),transparent 70%);
      animation:od2 24s ease-in-out infinite; }
.o3 { width:400px; height:400px; top:38%; left:32%;
      background:radial-gradient(circle,rgba(155,127,255,0.06),transparent 70%);
      animation:od3 35s ease-in-out infinite; }

@keyframes od1{0%,100%{transform:translate(0,0) scale(1)}40%{transform:translate(55px,70px) scale(1.08)}70%{transform:translate(-28px,45px) scale(0.95)}}
@keyframes od2{0%,100%{transform:translate(0,0) scale(1)}35%{transform:translate(-65px,-45px) scale(1.1)}65%{transform:translate(38px,65px) scale(0.9)}}
@keyframes od3{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(45px,-38px) scale(1.14)}}

.shell {
  position:relative; z-index:2;
  width:min(820px,100vw); height:100vh;
  display:flex; flex-direction:column;
}

header {
  flex-shrink:0;
  display:flex; align-items:center; gap:14px;
  padding:18px 32px;
  border-bottom:1px solid var(--b);
  background:rgba(5,8,15,0.82);
  backdrop-filter:blur(24px);
}

.hlogo {
  width:46px; height:46px; border-radius:15px; flex-shrink:0;
  background:linear-gradient(135deg,var(--cyan) 0%,var(--blue) 55%,var(--violet) 100%);
  display:flex; align-items:center; justify-content:center;
  font-family:'Syne',sans-serif; font-weight:800; font-size:1.05rem;
  color:var(--bg); animation:lpulse 4s ease-in-out infinite;
}
@keyframes lpulse{0%,100%{box-shadow:0 0 0 0 rgba(0,232,204,0.28)}50%{box-shadow:0 0 0 7px rgba(0,232,204,0)}}

.hinfo h1 { font-family:'Syne',sans-serif; font-size:1.06rem; font-weight:700; color:#fff; letter-spacing:-0.02em; }
.hinfo p  { font-size:0.7rem; color:var(--muted); margin-top:1px; letter-spacing:0.02em; }

.hright { margin-left:auto; display:flex; align-items:center; gap:10px; }

.mtag {
  background:var(--g); border:1px solid var(--b); border-radius:8px;
  padding:4px 10px; font-family:'Space Mono',monospace;
  font-size:0.62rem; color:var(--muted); letter-spacing:0.04em;
}

.hstatus {
  display:flex; align-items:center; gap:7px;
  font-family:'Space Mono',monospace; font-size:0.65rem;
  color:var(--green); letter-spacing:0.08em; text-transform:uppercase;
}
.hsdot { width:6px; height:6px; border-radius:50%; background:var(--green); animation:sdot 2s ease-in-out infinite; }
@keyframes sdot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.3;transform:scale(0.6)}}

/* ── Symptom progress bar ── */
#sympbar {
  display:none; flex-shrink:0;
  padding:8px 32px;
  border-bottom:1px solid var(--b);
  background:rgba(5,8,15,0.6);
  backdrop-filter:blur(12px);
}
#sympbar.visible { display:flex; align-items:center; gap:10px; }
.sympbar-label { font-family:'Space Mono',monospace; font-size:.62rem; color:var(--muted); letter-spacing:.06em; text-transform:uppercase; white-space:nowrap; }
.sympbar-tags  { display:flex; flex-wrap:wrap; gap:5px; flex:1; }
.sympbar-tag   {
  background:rgba(0,232,204,.08); border:1px solid rgba(0,232,204,.2);
  color:var(--cyan); border-radius:99px; padding:2px 9px;
  font-size:.7rem; animation:tagpop .3s cubic-bezier(.34,1.56,.64,1) both;
}
#sympbar-clear {
  font-family:'Space Mono',monospace; font-size:.6rem; color:var(--muted);
  background:none; border:1px solid var(--b); border-radius:6px;
  padding:3px 8px; cursor:pointer; white-space:nowrap;
  transition:border-color .2s,color .2s;
}
#sympbar-clear:hover { border-color:rgba(249,168,37,.4); color:var(--amber); }

#feed {
  flex:1; overflow-y:auto; padding:36px 32px 20px;
  display:flex; flex-direction:column; gap:22px;
  scroll-behavior:smooth;
}
#feed::-webkit-scrollbar{width:3px;}
#feed::-webkit-scrollbar-track{background:transparent;}
#feed::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:4px;}

#welcome {
  flex:1; display:flex; flex-direction:column;
  align-items:center; justify-content:center;
  text-align:center; gap:18px; padding:40px 20px;
  animation:fadeup .7s ease both;
}
.wring {
  width:96px; height:96px; border-radius:50%;
  border:1px solid rgba(0,232,204,0.18);
  display:flex; align-items:center; justify-content:center;
  font-size:42px; position:relative;
  animation:wbreathe 4s ease-in-out infinite;
}
.wring::before,.wring::after{content:'';position:absolute;border-radius:50%;border:1px solid rgba(0,232,204,0.1);}
.wring::before{width:122%;height:122%;animation:wexp 4s ease-in-out infinite .5s;}
.wring::after {width:148%;height:148%;animation:wexp 4s ease-in-out infinite 1s;}
@keyframes wbreathe{0%,100%{box-shadow:0 0 25px rgba(0,232,204,0.12)}50%{box-shadow:0 0 45px rgba(0,232,204,0.22)}}
@keyframes wexp{0%,100%{opacity:.5;transform:scale(1)}50%{opacity:.1;transform:scale(1.04)}}

#welcome h2 { font-family:'Syne',sans-serif; font-size:1.85rem; font-weight:700; color:#fff; letter-spacing:-0.04em; }
#welcome p  { font-size:.875rem; color:var(--muted); line-height:1.8; max-width:400px; }

.chips { display:flex; flex-wrap:wrap; gap:9px; justify-content:center; margin-top:4px; }
.chip {
  background:var(--g); border:1px solid var(--b); border-radius:99px;
  padding:8px 16px; font-size:.8rem; color:var(--muted);
  cursor:pointer; transition:all .2s;
}
.chip:hover { border-color:rgba(0,232,204,.35); color:var(--cyan); background:rgba(0,232,204,.06); transform:translateY(-1px); }

.msg { display:flex; gap:12px; align-items:flex-start; animation:msgin .45s cubic-bezier(.34,1.56,.64,1) both; }
.msg.user { flex-direction:row-reverse; }
@keyframes msgin{from{opacity:0;transform:translateY(18px) scale(.96)}to{opacity:1;transform:translateY(0) scale(1)}}

.av {
  width:34px; height:34px; border-radius:50%; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  font-size:14px; margin-top:3px;
}
.av.ai {
  background:linear-gradient(135deg,var(--cyan),var(--blue));
  color:var(--bg); font-family:'Syne',sans-serif;
  font-weight:800; font-size:.85rem;
  animation:avpulse 3s ease-in-out infinite;
}
@keyframes avpulse{0%,100%{box-shadow:0 0 10px rgba(0,232,204,.18)}50%{box-shadow:0 0 20px rgba(0,232,204,.42)}}
.av.user { background:var(--bg2); border:1px solid var(--b2); color:var(--muted); }

.bub {
  max-width:70%; padding:13px 18px;
  border-radius:var(--r); font-size:.88rem; line-height:1.72;
  border:1px solid var(--b); position:relative;
}
.msg.ai .bub {
  background:var(--g); backdrop-filter:blur(12px);
  border-top-left-radius:5px; padding-left:22px;
}
.msg.ai .bub::before {
  content:''; position:absolute; left:0; top:18%; bottom:18%;
  width:2px; border-radius:2px;
  background:linear-gradient(to bottom,var(--cyan),var(--blue)); opacity:.55;
}
.msg.user .bub {
  background:linear-gradient(140deg,rgba(0,232,204,.1),rgba(79,143,255,.08));
  border-color:rgba(0,232,204,.18); border-top-right-radius:5px; color:#fff;
}

.taglabel { font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-family:'Space Mono',monospace; display:block; margin-bottom:7px; }
.tags { display:flex; flex-wrap:wrap; gap:6px; }
.tag {
  background:rgba(0,232,204,.08); border:1px solid rgba(0,232,204,.22);
  color:var(--cyan); border-radius:99px; padding:3px 11px;
  font-size:.73rem; animation:tagpop .3s cubic-bezier(.34,1.56,.64,1) both;
}
@keyframes tagpop{from{opacity:0;transform:scale(.8)}to{opacity:1;transform:scale(1)}}

/* ── merge notice ── */
.merge-notice {
  font-size:.75rem; color:var(--muted); margin-top:8px;
  display:flex; align-items:center; gap:6px;
}
.merge-notice::before { content:''; width:14px; height:1px; background:var(--muted); display:inline-block; }

.optq { font-size:.85rem; color:var(--txt); margin-bottom:12px; line-height:1.6; }
.opts { display:flex; flex-wrap:wrap; gap:8px; }
.opt {
  background:var(--bg2); border:1px solid var(--b2); color:var(--txt);
  border-radius:99px; padding:8px 18px; font-size:.82rem;
  font-family:'Figtree',sans-serif; cursor:pointer; transition:all .2s;
}
.opt:hover:not(:disabled) { border-color:rgba(0,232,204,.5); color:var(--cyan); background:rgba(0,232,204,.07); transform:translateY(-1px); box-shadow:0 4px 14px rgba(0,232,204,.08); }
.opt.chosen { border-color:var(--cyan); color:var(--cyan); background:rgba(0,232,204,.08); }
.opt.denied { border-color:rgba(255,255,255,.05); color:var(--muted); opacity:.4; }
.opt:disabled { cursor:default; transform:none; }

.nomatch { display:flex; align-items:flex-start; gap:10px; background:rgba(249,168,37,.06); border:1px solid rgba(249,168,37,.2); border-radius:14px; padding:13px 16px; font-size:.85rem; color:var(--amber); line-height:1.6; }

.trow { display:flex; gap:12px; align-items:flex-start; animation:msgin .3s ease both; }
.tbub {
  background:var(--g); backdrop-filter:blur(12px);
  border:1px solid var(--b); border-radius:var(--r); border-top-left-radius:5px;
  padding:16px 20px 16px 24px; display:flex; gap:5px; align-items:center;
  position:relative;
}
.tbub::before { content:''; position:absolute; left:0; top:20%; bottom:20%; width:2px; border-radius:2px; background:linear-gradient(to bottom,var(--cyan),var(--blue)); opacity:.5; }
.td { width:7px; height:7px; border-radius:50%; animation:tdb 1.3s ease-in-out infinite; }
.td:nth-child(1){background:var(--cyan);}
.td:nth-child(2){background:var(--blue);animation-delay:.18s;}
.td:nth-child(3){background:var(--violet);animation-delay:.36s;}
@keyframes tdb{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-7px);opacity:1}}

.douter { width:100%; animation:drise .65s cubic-bezier(.22,.68,0,1.25) both; }
@keyframes drise{from{opacity:0;transform:translateY(24px) scale(.97)}to{opacity:1;transform:translateY(0) scale(1)}}

.dcard {
  background:linear-gradient(150deg,rgba(255,255,255,.04),rgba(255,255,255,.02));
  border:1px solid rgba(0,232,204,.18); border-radius:26px;
  overflow:hidden; backdrop-filter:blur(20px);
  box-shadow:0 0 0 1px rgba(0,232,204,.04),0 24px 80px rgba(0,0,0,.5),inset 0 1px 0 rgba(255,255,255,.05);
}
.dstripe { height:2px; background:linear-gradient(90deg,var(--cyan),var(--blue),var(--violet)); opacity:.65; }

.dtop {
  padding:28px 30px; display:flex; align-items:center; gap:24px;
  border-bottom:1px solid var(--b);
}

.arcbox { position:relative; width:100px; height:100px; flex-shrink:0; }
.arcsvg { width:100%; height:100%; transform:rotate(-90deg); }
.arcbg  { fill:none; stroke:rgba(255,255,255,.06); stroke-width:7; }
.arcfg  {
  fill:none; stroke-width:7; stroke-linecap:round; stroke:url(#cg);
  stroke-dasharray:263.9; stroke-dashoffset:263.9;
  transition:stroke-dashoffset 1.4s cubic-bezier(.22,.68,0,1.2) .35s;
}
.arccenter { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1px; }
.arcnum { font-family:'Space Mono',monospace; font-size:1.2rem; font-weight:700; color:#fff; line-height:1; }
.arclbl { font-size:.6rem; letter-spacing:.07em; text-transform:uppercase; color:var(--muted); }

.dtopinfo { flex:1; min-width:0; }
.dbadge {
  display:inline-flex; align-items:center; gap:6px;
  background:rgba(0,232,204,.08); border:1px solid rgba(0,232,204,.2);
  border-radius:99px; padding:4px 12px;
  font-size:.67rem; color:var(--cyan); font-family:'Space Mono',monospace;
  letter-spacing:.06em; text-transform:uppercase; margin-bottom:10px;
}
.dname { font-family:'Syne',sans-serif; font-size:1.45rem; font-weight:700; color:#fff; letter-spacing:-.03em; line-height:1.15; word-break:break-word; }

.dbody { padding:22px 30px; }
.dseclabel { font-family:'Space Mono',monospace; font-size:.63rem; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); margin-bottom:13px; }

.altitem { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
.altname { font-size:.83rem; color:var(--txt); flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.alttrack { flex:2; height:4px; background:rgba(255,255,255,.06); border-radius:99px; overflow:hidden; }
.altfill { height:100%; border-radius:99px; background:linear-gradient(90deg,rgba(0,232,204,.45),rgba(79,143,255,.45)); width:0%; transition:width 1.1s cubic-bezier(.22,.68,0,1.2) .55s; }
.altpct { font-family:'Space Mono',monospace; font-size:.72rem; color:var(--muted); width:40px; text-align:right; }

.dsep { height:1px; background:var(--b); margin:20px 0; }

.preclist { display:flex; flex-direction:column; gap:8px; }
.precitem {
  display:flex; align-items:flex-start; gap:12px;
  background:rgba(255,255,255,.02); border:1px solid var(--b); border-radius:14px;
  padding:11px 15px; font-size:.84rem; color:var(--txt); line-height:1.55;
  transition:border-color .2s,background .2s; animation:precin .4s ease both;
}
.precitem:hover { border-color:rgba(0,232,204,.15); background:rgba(0,232,204,.03); }
@keyframes precin{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}
.precn { font-family:'Space Mono',monospace; font-size:.63rem; background:rgba(0,232,204,.1); color:var(--cyan); border-radius:6px; padding:2px 6px; flex-shrink:0; margin-top:2px; }

.dfoot { padding:12px 30px; border-top:1px solid var(--b); font-size:.7rem; color:var(--muted); font-style:italic; display:flex; align-items:center; gap:8px; }
.dfdot { width:3px; height:3px; border-radius:50%; background:var(--muted); }

/* ── hint pill above input when mid-session ── */
.session-hint {
  display:none; text-align:center;
  font-size:.7rem; color:var(--cyan);
  margin-bottom:6px; letter-spacing:.01em;
  opacity:.7;
}
.session-hint.visible { display:block; }

.dock { flex-shrink:0; padding:10px 32px 26px; }
.ishell {
  display:flex; align-items:flex-end; gap:10px;
  background:rgba(255,255,255,.04); border:1px solid var(--b);
  border-radius:22px; padding:10px 10px 10px 20px;
  position:relative; overflow:hidden;
  transition:border-color .3s,box-shadow .3s;
}
.ishell:focus-within { border-color:rgba(0,232,204,.4); box-shadow:0 0 0 4px rgba(0,232,204,.05),0 12px 40px rgba(0,0,0,.25); }
.ishell::after { content:''; position:absolute; bottom:0; left:8%; right:8%; height:1px; background:linear-gradient(90deg,transparent,var(--cyan),transparent); transform:scaleX(0); opacity:0; transition:transform .4s ease,opacity .3s; }
.ishell:focus-within::after { transform:scaleX(1); opacity:.5; }

#msg { flex:1; background:transparent; border:none; outline:none; color:var(--txt); font-family:'Figtree',sans-serif; font-size:.9rem; line-height:1.6; resize:none; max-height:130px; padding:3px 0; }
#msg::placeholder { color:var(--muted); }

.sendbtn {
  width:42px; height:42px; border-radius:14px; flex-shrink:0;
  background:linear-gradient(135deg,var(--cyan),var(--blue));
  border:none; cursor:pointer; color:var(--bg);
  display:flex; align-items:center; justify-content:center;
  transition:transform .15s,box-shadow .2s,opacity .2s;
}
.sendbtn svg { width:17px; height:17px; }
.sendbtn:hover:not(:disabled) { transform:scale(1.08); box-shadow:0 0 22px rgba(0,232,204,.45); }
.sendbtn:active:not(:disabled) { transform:scale(.95); }
.sendbtn:disabled { opacity:.3; cursor:not-allowed; }

.dhint { text-align:center; font-size:.68rem; color:var(--muted); margin-top:9px; letter-spacing:.01em; }

@keyframes fadeup{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
</style>
</head>
<body>

<svg width="0" height="0" style="position:absolute;pointer-events:none">
  <defs>
    <linearGradient id="cg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#00e8cc"/>
      <stop offset="100%" stop-color="#4f8fff"/>
    </linearGradient>
  </defs>
</svg>

<canvas id="bg"></canvas>
<div class="orb o1"></div>
<div class="orb o2"></div>
<div class="orb o3"></div>

<div class="shell">
  <header>
    <div class="hlogo">&#198;</div>
    <div class="hinfo">
      <h1>Anti Medical</h1>
      <p>Symptom Analysis &amp; Differential Diagnosis</p>
    </div>
    <div class="hright">
      <div class="mtag">v0.0</div>
      <div class="hstatus"><div class="hsdot"></div>Online</div>
    </div>
  </header>

  <!-- Live symptom bar — visible once session starts -->
  <div id="sympbar">
    <span class="sympbar-label">Tracking</span>
    <div class="sympbar-tags" id="sympbar-tags"></div>
    <button id="sympbar-clear" onclick="clearSession()" title="Start over">&#10005; Clear</button>
  </div>

  <div id="feed">
    <div id="welcome">
      <div class="wring">&#x1FA7A;</div>
      <h2>How are you feeling?</h2>
      <p>Describe your symptoms in plain language. Anti will analyse them and generate a detailed diagnosis report.</p>
      <div class="chips">
        <span class="chip" onclick="useChip('I have fever, headache and body aches')">&#127777; Fever &amp; headache</span>
        <span class="chip" onclick="useChip('I have chest pain and shortness of breath')">&#128148; Chest pain</span>
        <span class="chip" onclick="useChip('I feel nauseous with stomach pain and vomiting')">&#129314; Nausea &amp; stomach pain</span>
        <span class="chip" onclick="useChip('I have a cough, runny nose and sore throat')">&#129320; Cough &amp; sore throat</span>
        <span class="chip" onclick="useChip('I feel very tired with joint pain and fatigue')">&#128564; Fatigue &amp; joint pain</span>
      </div>
    </div>
  </div>

  <div class="dock">
    <div class="session-hint" id="session-hint">
      &#x2295; You can keep describing more symptoms to refine the analysis
    </div>
    <div class="ishell">
      <textarea id="msg" rows="1" placeholder="Describe your symptoms&#8230;" autocomplete="off"></textarea>
      <button class="sendbtn" id="sendbtn" onclick="sendMsg()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
        </svg>
      </button>
    </div>
    <div class="dhint">For educational purposes only &middot; Not a substitute for professional medical advice</div>
  </div>
</div>

<script>
/* ── Canvas particle network ── */
(function(){
  const c=document.getElementById('bg'),ctx=c.getContext('2d');
  let W,H,nodes=[];
  function resize(){W=c.width=innerWidth;H=c.height=innerHeight;}
  resize(); addEventListener('resize',resize);
  for(let i=0;i<55;i++) nodes.push({
    x:Math.random()*W, y:Math.random()*H,
    vx:(Math.random()-.5)*.22, vy:(Math.random()-.5)*.22,
    r:1+Math.random()*1.8, o:.2+Math.random()*.4
  });
  function draw(){
    ctx.clearRect(0,0,W,H);
    nodes.forEach((n,i)=>{
      n.x+=n.vx; n.y+=n.vy;
      if(n.x<0||n.x>W)n.vx*=-1; if(n.y<0||n.y>H)n.vy*=-1;
      ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,Math.PI*2);
      ctx.fillStyle=`rgba(0,232,204,${n.o*.55})`; ctx.fill();
      for(let j=i+1;j<nodes.length;j++){
        const m=nodes[j],dx=m.x-n.x,dy=m.y-n.y,d=Math.sqrt(dx*dx+dy*dy);
        if(d<130){
          ctx.beginPath(); ctx.moveTo(n.x,n.y); ctx.lineTo(m.x,m.y);
          ctx.strokeStyle=`rgba(0,232,204,${(1-d/130)*.065})`; ctx.lineWidth=.7; ctx.stroke();
        }
      }
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

/* ══════════════════════════════
   STATE
   ══════════════════════════════ */
let S = { matched: [], denied: [] };
let busy         = false;
let uid          = 0;
/*
  sessionActive:
    false → next sendMsg() is a FRESH start (no prior symptoms)
    true  → next sendMsg() MERGES with existing S.matched
  Starts false. Set to true once options are returned.
  Reset to false after a result card is shown OR clearSession() is called.
*/
let sessionActive = false;

const feed    = document.getElementById('feed');
const msgEl   = document.getElementById('msg');
const sendBtn = document.getElementById('sendbtn');

/* ── Textarea auto-resize ── */
msgEl.addEventListener('input',()=>{
  msgEl.style.height='auto';
  msgEl.style.height=Math.min(msgEl.scrollHeight,130)+'px';
});
msgEl.addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); sendMsg(); }
});

/* ── Helpers ── */
const esc     = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const delay   = ms => new Promise(r=>setTimeout(r,ms));
const scroll  = () => { feed.scrollTop = feed.scrollHeight; };
const setLoad = v  => { busy = v; sendBtn.disabled = v; };
const hideWelcome = () => document.getElementById('welcome')?.remove();

/* ── Symptom bar ── */
function updateSympBar(matched){
  const bar   = document.getElementById('sympbar');
  const inner = document.getElementById('sympbar-tags');
  if(!matched||matched.length===0){ bar.classList.remove('visible'); return; }
  bar.classList.add('visible');
  inner.innerHTML = matched.map(s=>
    `<span class="sympbar-tag">${s.replace(/_/g,' ')}</span>`
  ).join('');
}

/* ── Clear / reset session ── */
function clearSession(){
  S = { matched:[], denied:[] };
  sessionActive = false;
  updateSympBar([]);
  document.getElementById('session-hint').classList.remove('visible');
  addAI(`<span style="color:var(--muted);font-size:.85rem;">Session cleared. Describe new symptoms whenever you're ready.</span>`);
}

/* ── User bubble ── */
function addUser(text){
  const el=document.createElement('div');
  el.className='msg user';
  el.innerHTML=`<div class="av user">&#128100;</div><div class="bub">${esc(text)}</div>`;
  feed.appendChild(el); scroll();
}

/* ── Typing indicator ── */
function showTyping(){
  const el=document.createElement('div');
  el.id='typing'; el.className='trow';
  el.innerHTML=`<div class="av ai">&#198;</div><div class="tbub"><div class="td"></div><div class="td"></div><div class="td"></div></div>`;
  feed.appendChild(el); scroll();
}
function hideTyping(){ document.getElementById('typing')?.remove(); }

/* ── AI HTML bubble ── */
function addAI(html){
  const wrap=document.createElement('div'); wrap.className='msg ai';
  wrap.innerHTML=`<div class="av ai">&#198;</div><div class="bub">${html}</div>`;
  feed.appendChild(wrap); scroll();
}

/* ══════════════════════════════
   RENDER RESPONSE
   ══════════════════════════════ */
async function render(resp, detected, wasMerge){
  hideTyping();

  /* Show detected/merged symptom tags */
  if(detected?.length && resp.type!=='no_symptoms'){
    const tags = detected.map(s=>`<span class="tag">${s.replace(/_/g,' ')}</span>`).join('');
    const mergeNote = wasMerge
      ? `<div class="merge-notice">Added to existing symptoms</div>`
      : '';
    addAI(`<span class="taglabel">Symptoms detected</span><div class="tags">${tags}</div>${mergeNote}`);
    await delay(200);
  }

  if(resp.type==='no_symptoms' || resp.type==='no_match'){
    addAI(`<div class="nomatch">&#9888;&#xFE0F;&nbsp; Couldn't identify specific symptoms. Try something like: <em>"I have a fever, sore throat, and fatigue."</em></div>`);
    /* Don't kill the session — let them retry */

  } else if(resp.type==='options'){
    /* ── Render follow-up option buttons ── */
    const btns = resp.options.map(o=>
      `<button class="opt" data-sym="${o}" onclick="choose('${o}',this)">${o.replace(/_/g,' ')}</button>`
    ).join('');
    addAI(`<div class="optq">${esc(resp.question)}</div><div class="opts">${btns}</div>`);
    /* Mid-session: type-in merges from now on */
    sessionActive = true;
    document.getElementById('session-hint').classList.add('visible');

  } else if(resp.type==='result'){
    await delay(100);
    buildDiagCard(resp);
    /* ── After result: auto-reset so next message is a fresh case ── */
    S = { matched:[], denied:[] };
    sessionActive = false;
    updateSympBar([]);
    document.getElementById('session-hint').classList.remove('visible');
  }

  scroll();
  setLoad(false);
}

/* ══════════════════════════════
   DIAGNOSIS CARD
   ══════════════════════════════ */
function buildDiagCard(resp){
  const top  = resp.diseases[0];
  const alts = resp.diseases.slice(1);
  const id   = 'a'+(++uid);
  const circ = 2*Math.PI*43; // r=43 → 270.2

  const altRows = alts.map(d=>`
    <div class="altitem">
      <div class="altname">${esc(d.name)}</div>
      <div class="alttrack"><div class="altfill" data-w="${d.confidence}"></div></div>
      <div class="altpct">${d.confidence}%</div>
    </div>`).join('');

  const precs = resp.precautions.map((p,i)=>`
    <div class="precitem" style="animation-delay:${i*.07}s">
      <span class="precn">0${i+1}</span><span>${esc(p)}</span>
    </div>`).join('');

  const ts = new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});

  const outer = document.createElement('div');
  outer.className = 'douter';
  outer.innerHTML = `
    <div class="dcard">
      <div class="dstripe"></div>
      <div class="dtop">
        <div class="arcbox">
          <svg class="arcsvg" viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg">
            <circle class="arcbg" cx="48" cy="48" r="43"/>
            <circle class="arcfg" id="${id}" cx="48" cy="48" r="43"
              stroke-dasharray="${circ.toFixed(2)}" stroke-dashoffset="${circ.toFixed(2)}"/>
          </svg>
          <div class="arccenter">
            <div class="arcnum" id="${id}n">0%</div>
            <div class="arclbl">match</div>
          </div>
        </div>
        <div class="dtopinfo">
          <div class="dbadge">&#128302;&nbsp;Diagnosis Report</div>
          <div class="dname">${esc(top.name)}</div>
        </div>
      </div>
      <div class="dbody">
        ${alts.length ? `<div class="dseclabel">Other candidates</div>${altRows}<div class="dsep"></div>` : ''}
        <div class="dseclabel">Recommended precautions</div>
        <div class="preclist">${precs}</div>
      </div>
      <div class="dfoot">
        &#9200; ${ts}<div class="dfdot"></div>Informational only<div class="dfdot"></div>Consult a licensed physician.
      </div>
    </div>`;

  feed.appendChild(outer); scroll();

  /* Animate arc + counter */
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    const arcEl = document.getElementById(id);
    const numEl = document.getElementById(id+'n');
    if(arcEl) arcEl.style.strokeDashoffset = circ*(1 - top.confidence/100);
    let cur=0; const tgt=top.confidence;
    const step=()=>{
      cur=Math.min(cur+1.4, tgt);
      if(numEl) numEl.textContent=Math.floor(cur)+'%';
      if(cur<tgt) requestAnimationFrame(step);
    };
    setTimeout(step,380);
    outer.querySelectorAll('.altfill').forEach(b=>{
      if(b.dataset.w) b.style.width=b.dataset.w+'%';
    });
  }));
}

/* ══════════════════════════════
   SEND MESSAGE
   ══════════════════════════════
   Key logic:
   - sessionActive=false  → fresh start (reset S before sending)
   - sessionActive=true   → MERGE (send accumulate:true with existing S)
   ══════════════════════════════ */
async function sendMsg(){
  if(busy) return;
  const text = msgEl.value.trim();
  if(!text) return;

  hideWelcome();
  setLoad(true);
  msgEl.value=''; msgEl.style.height='auto';
  addUser(text);

  /* Decide whether to merge or start fresh */
  const accumulate = sessionActive && S.matched.length > 0;
  if(!accumulate){
    /* Fresh start — wipe local state */
    S = { matched:[], denied:[] };
    sessionActive = false;
  }

  await delay(320); showTyping();

  try{
    const res = await fetch('/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        message:     text,
        matched:     S.matched,   // empty on fresh, existing on merge
        denied:      S.denied,
        accumulate:  accumulate   // ← tells backend to merge
      })
    });
    const data = await res.json();
    S = { matched: data.matched, denied: data.denied };
    updateSympBar(S.matched);
    await delay(750);
    await render(data.response, data.detected, accumulate);
  } catch(e){
    hideTyping(); setLoad(false); console.error(e);
  }
}

/* ══════════════════════════════
   CHOOSE OPTION
   ══════════════════════════════
   Marks chosen button, collects all sibling
   options as denied, sends full state to backend.
   ══════════════════════════════ */
async function choose(sym, btn){
  if(busy) return;

  const allBtns = [...btn.closest('.opts').querySelectorAll('.opt')];
  const newDenied = allBtns.filter(b=>b.dataset.sym!==sym).map(b=>b.dataset.sym);

  /* Visual feedback */
  allBtns.forEach(b=>{
    b.disabled = true;
    if(b.dataset.sym===sym) b.classList.add('chosen');
    else b.classList.add('denied');
  });

  setLoad(true);
  addUser('Yes \u2014 '+sym.replace(/_/g,' '));
  await delay(320); showTyping();

  /* Build the definitive denied list (existing + siblings not chosen) */
  const fullDenied = [...new Set([...S.denied, ...newDenied])];

  try{
    const res = await fetch('/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        choice:  sym,
        matched: S.matched,    // carry ALL accumulated symptoms
        denied:  fullDenied    // carry ALL denied symptoms
      })
    });
    const data = await res.json();
    /* ── Update state from server response ── */
    S = { matched: data.matched, denied: data.denied };
    updateSympBar(S.matched);
    await delay(850);
    await render(data.response, null, false);
  } catch(e){
    hideTyping(); setLoad(false); console.error(e);
  }
}

/* ── Starter chips ── */
function useChip(text){ msgEl.value=text; msgEl.focus(); }
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(debug=True)
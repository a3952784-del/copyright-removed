import os, re, uuid, sqlite3, subprocess
from pathlib import Path
from urllib.parse import urlparse
import requests
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext

BASE=Path(__file__).resolve().parent.parent
UPLOADS=BASE/"uploads"; EXPORTS=BASE/"exports"; STATIC=BASE/"app"/"static"
UPLOADS.mkdir(exist_ok=True); EXPORTS.mkdir(exist_ok=True)
DB=BASE/"clipfix.sqlite3"
app=FastAPI(title="ClipFix AI")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("CLIPFIX_SECRET_KEY","CHANGE-ME-before-deploying"), same_site="lax", https_only=os.getenv("HTTPS_ONLY","0")=="1")
app.mount("/static",StaticFiles(directory=STATIC),name="static")
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
MAX=250*1024*1024
EXTS={".mp4",".mov",".m4v",".webm",".mkv"}

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
with conn() as c:
 c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, pw TEXT)")
 c.execute("CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY, uid INTEGER, name TEXT, src TEXT, out TEXT, status TEXT DEFAULT 'uploaded')")
def esc(s):
 return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")
def user(req):
 uid=req.session.get("uid")
 if not uid:return None
 with conn() as c:return c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
def video(vid,uid):
 with conn() as c:r=c.execute("SELECT * FROM videos WHERE id=? AND uid=?",(vid,uid)).fetchone()
 if not r:raise HTTPException(404,"Video not found")
 return r

@app.get("/",response_class=HTMLResponse)
def home(req:Request):
 u=user(req)
 if not u:return RedirectResponse("/login",303)
 with conn() as c: rows=c.execute("SELECT * FROM videos WHERE uid=? ORDER BY rowid DESC",(u["id"],)).fetchall()
 cards=""
 for v in rows:
  dl=f'<a class="download" href="/download/{v["id"]}">Download edited MP4 ↓</a>' if v["out"] and Path(v["out"]).exists() else ""
  cards+=f'''<article class="video-card"><div class="file-icon">▶</div><div class="video-info"><b>{esc(v["name"])}</b><small>Status: {esc(v["status"])}</small>
  <form action="/edit/{v["id"]}" method="post" enctype="multipart/form-data" class="edit-form">
  <label>Speed<select name="speed"><option value="1">Normal</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option><option value="0.75">0.75×</option></select></label>
  <label>Pitch<select name="pitch"><option value="1">Original</option><option value="1.15">Higher</option><option value="0.85">Lower</option></select></label>
  <label>Zoom<select name="zoom"><option value="1">None</option><option value="1.08">Subtle</option><option value="1.18">Strong</option></select></label>
  <label class="upload-effect">Optional sound effect<input type="file" name="effect" accept="audio/*"></label><button class="button small">Apply & Export MP4</button></form>{dl}</div></article>'''
 return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ClipFix AI</title><link rel="stylesheet" href="/static/style.css"></head><body>
 <nav><a class="brand" href="/">✦ ClipFix <span>AI</span></a><div class="nav-right">Signed in as <b>{esc(u["username"])}</b><a href="/logout">Log out</a></div></nav><main>
 <section class="hero"><div class="pill">AI-POWERED VIDEO WORKSPACE</div><h1>Make every clip<br><em>hit different.</em></h1><p>Upload videos you own or are authorized to edit. Apply speed, pitch and zoom effects, then export a polished MP4.</p></section>
 <section class="panel"><h2>＋ Add a video</h2><form action="/upload" method="post" enctype="multipart/form-data" class="upload-form"><label class="drop"><span class="upload-symbol">↑</span><b>Choose a video file</b><small>MP4, MOV, WEBM or MKV · max 250 MB</small><input required type="file" name="video" accept="video/*"></label><button class="button">Upload video</button></form>
 <details><summary>Import an authorized direct-video URL</summary><p class="muted">Only direct HTTPS links to video files you have permission to download. YouTube watch-page URLs are not supported.</p><form action="/import-url" method="post" class="url-form"><input name="video_url" type="url" placeholder="https://example.com/video.mp4" required><button class="button">Import URL</button></form></details></section>
 <section class="library"><div class="section-head"><h2>Your projects</h2><span>{len(rows)} videos</span></div>{cards or '<div class="empty">Your workspace is ready.<br><small>Upload your first video to get started.</small></div>'}</section>
 <footer>ClipFix AI · Edit responsibly. Only use content you own or are authorized to use.</footer></main></body></html>''')

def authpage(register=False):
 title="Create your account" if register else "Welcome back"; action="/register" if register else "/login"
 switch='<p class="auth-switch">Already registered? <a href="/login">Log in</a></p>' if register else '<p class="auth-switch">New to ClipFix? <a href="/register">Create an account</a></p>'
 return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · ClipFix AI</title><link rel="stylesheet" href="/static/style.css"></head><body class="auth-body"><nav><a class="brand" href="/">✦ ClipFix <span>AI</span></a></nav><main class="auth-wrap"><div class="pill">YOUR CREATIVE WORKSPACE</div><h1>{title}</h1><p class="muted">Your clips. Your edits. Your workflow.</p><form class="auth-form" method="post" action="{action}"><label>Username<input name="username" minlength="3" maxlength="40" required></label><label>Password<input type="password" name="password" minlength="8" required></label><button class="button">{'Create account' if register else 'Log in'}</button></form>{switch}</main></body></html>''')
@app.get("/login",response_class=HTMLResponse)
def loginpage():return authpage()
@app.get("/register",response_class=HTMLResponse)
def regpage():return authpage(True)
@app.post("/register")
def register(req:Request,username:str=Form(...),password:str=Form(...)):
 username=username.strip()
 if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}",username) or len(password)<8:raise HTTPException(400,"Use a 3–40 character username and an 8+ character password.")
 try:
  with conn() as c:cur=c.execute("INSERT INTO users(username,pw) VALUES(?,?)",(username,pwd.hash(password)));req.session["uid"]=cur.lastrowid
 except sqlite3.IntegrityError:raise HTTPException(409,"Username already taken.")
 return RedirectResponse("/",303)
@app.post("/login")
def login(req:Request,username:str=Form(...),password:str=Form(...)):
 with conn() as c:u=c.execute("SELECT * FROM users WHERE username=?",(username.strip(),)).fetchone()
 if not u or not pwd.verify(password,u["pw"]):raise HTTPException(401,"Incorrect username or password.")
 req.session.clear();req.session["uid"]=u["id"];return RedirectResponse("/",303)
@app.get("/logout")
def logout(req:Request):req.session.clear();return RedirectResponse("/login",303)

@app.post("/upload")
async def upload(req:Request,video:UploadFile=File(...)):
 u=user(req)
 if not u:return RedirectResponse("/login",303)
 ext=Path(video.filename or "").suffix.lower()
 if ext not in EXTS:raise HTTPException(415,"Upload MP4, MOV, M4V, WEBM, or MKV.")
 vid=str(uuid.uuid4());path=UPLOADS/f"{vid}{ext}";size=0
 with path.open("wb") as out:
  while True:
   chunk=await video.read(1024*1024)
   if not chunk:break
   size+=len(chunk)
   if size>MAX:path.unlink(missing_ok=True);raise HTTPException(413,"Maximum upload size is 250 MB.")
   out.write(chunk)
 with conn() as c:c.execute("INSERT INTO videos(id,uid,name,src) VALUES(?,?,?,?)",(vid,u["id"],Path(video.filename).name,str(path)))
 return RedirectResponse("/",303)

@app.post("/import-url")
def import_url(req:Request,video_url:str=Form(...)):
 u=user(req)
 if not u:return RedirectResponse("/login",303)
 p=urlparse(video_url);host=(p.hostname or "").lower()
 if p.scheme!="https" or not host or host in {"youtube.com","www.youtube.com","m.youtube.com","youtu.be","www.youtu.be","localhost","127.0.0.1"} or host.endswith(".local"):
  raise HTTPException(400,"Use an HTTPS direct-video file URL; YouTube pages are not supported.")
 vid=str(uuid.uuid4());path=UPLOADS/f"{vid}.mp4"
 try:
  with requests.get(video_url,stream=True,timeout=(5,20),allow_redirects=False) as r:
   if r.status_code!=200:raise HTTPException(400,"Could not fetch direct video URL.")
   if not (r.headers.get("content-type","").lower().startswith("video/") or "octet-stream" in r.headers.get("content-type","").lower()):raise HTTPException(415,"URL did not return a video file.")
   size=0
   with path.open("wb") as f:
    for chunk in r.iter_content(1024*1024):
     if not chunk:continue
     size+=len(chunk)
     if size>MAX:path.unlink(missing_ok=True);raise HTTPException(413,"Maximum size is 250 MB.")
     f.write(chunk)
 except requests.RequestException:
  path.unlink(missing_ok=True);raise HTTPException(400,"Unable to import URL.")
 with conn() as c:c.execute("INSERT INTO videos(id,uid,name,src) VALUES(?,?,?,?)",(vid,u["id"],Path(p.path).name or "Imported video.mp4",str(path)))
 return RedirectResponse("/",303)

@app.post("/edit/{vid}")
async def edit(req:Request,vid:str,speed:float=Form(1),pitch:float=Form(1),zoom:float=Form(1),effect:UploadFile|None=File(None)):
 u=user(req)
 if not u:return RedirectResponse("/login",303)
 row=video(vid,u["id"]);inp=Path(row["src"])
 if not inp.exists():raise HTTPException(404,"Original file missing.")
 if speed not in {0.75,1.0,1.25,1.5,2.0} or pitch not in {0.85,1.0,1.15} or zoom not in {1.0,1.08,1.18}:raise HTTPException(400,"Invalid setting.")
 out=EXPORTS/f"{vid}-edited.mp4";cmd=["ffmpeg","-y","-i",str(inp)];effect_path=None
 if effect and effect.filename:
  data=await effect.read(20*1024*1024+1)
  if len(data)>20*1024*1024:raise HTTPException(413,"Sound effect must be under 20 MB.")
  effect_path=UPLOADS/f"{vid}-fx-{uuid.uuid4().hex[:6]}{Path(effect.filename).suffix[:8]}";effect_path.write_bytes(data);cmd+=["-i",str(effect_path)]
 vf=[]
 if zoom>1:vf.append(f"scale=iw*{zoom}:ih*{zoom},crop=iw/{zoom}:ih/{zoom}")
 if speed!=1:vf.append(f"setpts=PTS/{speed}")
 if vf:cmd+=["-vf",",".join(vf)]
 af=[]
 if pitch!=1:af.append(f"asetrate=44100*{pitch},aresample=44100")
 if speed!=1:
  remain=speed
  while remain>2:af.append("atempo=2");remain/=2
  while remain<0.5:af.append("atempo=0.5");remain/=0.5
  af.append(f"atempo={remain}")
 if effect_path:
  cmd+=["-filter_complex","[0:a]aformat=sample_rates=44100:channel_layouts=stereo[orig];[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.7[fx];[orig][fx]amix=inputs=2:duration=first[mix]","-map","0:v:0","-map","[mix]"]
 elif af:cmd+=["-af",",".join(af)]
 cmd+=["-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-movflags","+faststart",str(out)]
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=900)
  if p.returncode:out.unlink(missing_ok=True);raise HTTPException(422,"FFmpeg could not process this file. Check its audio/video streams.")
 except FileNotFoundError:raise HTTPException(503,"FFmpeg is not installed on this server.")
 except subprocess.TimeoutExpired:out.unlink(missing_ok=True);raise HTTPException(408,"Processing timed out; try a shorter video.")
 finally:
  if effect_path:effect_path.unlink(missing_ok=True)
 with conn() as c:c.execute("UPDATE videos SET out=?,status='exported' WHERE id=? AND uid=?",(str(out),vid,u["id"]))
 return RedirectResponse("/",303)
@app.get("/download/{vid}")
def download(req:Request,vid:str):
 u=user(req)
 if not u:return RedirectResponse("/login",303)
 row=video(vid,u["id"]);p=Path(row["out"]) if row["out"] else None
 if not p or not p.exists():raise HTTPException(404,"No edited export yet.")
 return FileResponse(p,media_type="video/mp4",filename=f"clipfix-{vid}.mp4")
@app.get("/health")
def health():return {"status":"ok","app":"ClipFix AI"}

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import Any, List, Optional, Literal
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os, uuid, secrets, bcrypt, jwt, logging, asyncio, json, resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Customer Feedback Platform API")
api = APIRouter(prefix="/api")
JWT_SECRET = os.environ["JWT_SECRET"]
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "")
if RESEND_API_KEY: resend.api_key = RESEND_API_KEY
log = logging.getLogger("feedback")

def now(): return datetime.now(timezone.utc).isoformat()
def clean(doc):
    if not doc: return None
    doc = dict(doc); doc.pop("_id", None); return doc
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): return bcrypt.checkpw(p.encode(), h.encode())
def token(uid): return jwt.encode({"sub": uid, "exp": datetime.now(timezone.utc)+timedelta(days=7), "type":"access"}, JWT_SECRET, algorithm="HS256")

# ---------- Schemas ----------
class RegisterIn(BaseModel): full_name: str = Field(min_length=2); email: EmailStr; password: str = Field(min_length=8)
class LoginIn(BaseModel): email: EmailStr; password: str
class WorkspaceIn(BaseModel): name: str = Field(min_length=2); business_type: str = "Other"; logo_url: str = ""; website: str = ""; location: str = ""; description: str = ""
class QuestionIn(BaseModel): question_text: str; question_type: str = "rating"; required: bool = True; description: str = ""; options: List[str] = []
class TemplateIn(BaseModel): name: str; description: str = ""; questions: List[QuestionIn] = []; location_id: Optional[str] = None
class AnswerIn(BaseModel): question_id: str; value: Any
class ResponseIn(BaseModel): answers: List[AnswerIn]
class InviteIn(BaseModel): email: EmailStr; role: Literal["editor", "viewer"] = "editor"
class RoleUpdateIn(BaseModel): role: Literal["editor", "viewer"]
class LocationIn(BaseModel): name: str = Field(min_length=1); address: str = ""; city: str = ""; phone: str = ""

# ---------- Auth helpers ----------
async def current_user(request: Request):
    raw = request.headers.get("Authorization", "").replace("Bearer ", "") or request.cookies.get("access_token")
    if not raw: raise HTTPException(401, "Please sign in to continue")
    try: payload = jwt.decode(raw, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(401, "Your session has expired")
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id":0, "password_hash":0})
    if not user: raise HTTPException(401, "User not found")
    return user

async def active_workspace(user):
    """Return the workspace the user owns OR is a member of (owner preferred)."""
    ws = await db.workspaces.find_one({"owner_id": user["id"]}, {"_id":0})
    if ws: ws["role"] = "owner"; return ws
    member = await db.workspace_members.find_one({"user_id": user["id"], "status": "active"}, {"_id":0})
    if not member: return None
    ws = await db.workspaces.find_one({"id": member["workspace_id"]}, {"_id":0})
    if ws: ws["role"] = member["role"]
    return ws

def require_role(ws, *roles):
    if not ws: raise HTTPException(400, "Create your business first")
    if ws.get("role") not in roles: raise HTTPException(403, "You don't have permission for this action")

# ---------- Email helper ----------
async def send_email(to: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        log.info(f"[email skipped — RESEND_API_KEY not set] to={to} subject={subject}")
        return False
    try:
        await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": html})
        return True
    except Exception as e:
        log.error(f"Resend send failed: {e}"); return False

# ---------- Auth routes ----------
@api.post("/auth/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}): raise HTTPException(409, "An account with this email already exists")
    user = {"id":str(uuid.uuid4()), "full_name":data.full_name, "email":email, "password_hash":hash_password(data.password), "created_at":now()}
    await db.users.insert_one(user)
    # Auto-link any pending invites for this email
    await db.workspace_members.update_many({"invite_email": email, "status": "pending"}, {"$set": {"user_id": user["id"]}})
    access = token(user["id"]); response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=604800)
    return {"user":{k:v for k,v in user.items() if k not in ("password_hash","_id")}, "access_token":access}

@api.post("/auth/login")
async def login(data: LoginIn, response: Response):
    identifier = data.email.lower()
    attempt = await db.login_attempts.find_one({"identifier":identifier}, {"_id":0})
    if attempt and attempt.get("locked_until","") > now(): raise HTTPException(429, "Too many attempts. Please try again in 15 minutes")
    user = await db.users.find_one({"email":identifier})
    if not user or not verify_password(data.password, user["password_hash"]):
        count = (attempt.get("count",0) if attempt else 0) + 1
        await db.login_attempts.update_one({"identifier":identifier},{"$set":{"identifier":identifier,"count":count,"locked_until":(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat() if count>=5 else ""}},upsert=True)
        raise HTTPException(401, "Incorrect email or password")
    await db.login_attempts.delete_one({"identifier":identifier})
    access = token(user["id"]); response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=604800)
    return {"user":{k:v for k,v in user.items() if k not in ("password_hash","_id")}, "access_token":access}

@api.post("/auth/logout")
async def logout(response: Response): response.delete_cookie("access_token"); return {"ok":True}
@api.get("/auth/me")
async def me(user=Depends(current_user)): return user

# ---------- Workspaces ----------
@api.get("/workspaces")
async def workspaces(user=Depends(current_user)):
    owned = [clean(x) async for x in db.workspaces.find({"owner_id":user["id"]}, {"_id":0})]
    for w in owned: w["role"] = "owner"
    member_ids = [m["workspace_id"] async for m in db.workspace_members.find({"user_id":user["id"], "status":"active"}, {"_id":0})]
    extras = [clean(x) async for x in db.workspaces.find({"id":{"$in":member_ids}}, {"_id":0})]
    return owned + extras

@api.post("/workspaces")
async def create_workspace(data: WorkspaceIn, user=Depends(current_user)):
    if await db.workspaces.find_one({"owner_id":user["id"]}): raise HTTPException(409, "You already have a workspace")
    ws = {"id":str(uuid.uuid4()), "owner_id":user["id"], **data.model_dump(), "created_at":now()}
    await db.workspaces.insert_one(ws); return clean(ws)

# ---------- Templates ----------
PRESETS = {
 "Restaurant Experience":[("How would you rate your overall experience?","rating"),("How would you rate the food quality?","rating"),("How would you rate our service?","rating"),("Would you recommend us?","yesno"),("Tell us more about your experience.","longtext")],
 "Product Purchase":[("How would you rate your purchase?","rating"),("Did the product meet your expectations?","yesno"),("What could we improve?","longtext")],
 "Service Experience":[("How would you rate our service?","rating"),("Was your issue resolved?","yesno"),("Share any additional feedback.","longtext")],
 "General Customer Feedback":[("How was your overall experience?","rating"),("Would you recommend us?","yesno"),("Tell us more.","longtext")]
}
def template_doc(data, ws, preset=None):
    questions=[]
    source = preset or [(q.question_text, q.question_type) for q in data.questions]
    for i,(text,typ) in enumerate(source):
        questions.append({"id":str(uuid.uuid4()),"question_text":text,"question_type":typ,"required":True,"description":"","options":["Yes","No"] if typ=="yesno" else [],"sort_order":i})
    return {"id":str(uuid.uuid4()),"workspace_id":ws["id"],"name":data.name,"description":data.description,"status":"DRAFT","public_slug":"","published_at":None,"questions":questions,"location_id":getattr(data,"location_id",None),"created_at":now(),"updated_at":now()}

@api.get("/templates")
async def templates(user=Depends(current_user)):
    ws = await active_workspace(user)
    return [] if not ws else [clean(x) async for x in db.templates.find({"workspace_id":ws["id"]},{"_id":0})]

@api.get("/templates/presets")
async def presets(user=Depends(current_user)):
    return [{"name":k,"question_count":len(v),"questions":[q[0] for q in v]} for k,v in PRESETS.items()]

@api.post("/templates")
async def create_template(data: TemplateIn, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    doc = template_doc(data, ws); await db.templates.insert_one(doc); return clean(doc)

@api.post("/templates/from-preset/{name}")
async def create_preset(name: str, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    if name not in PRESETS: raise HTTPException(404, "Template preset not found")
    data = TemplateIn(name=name, description="A ready-to-use feedback form.")
    doc = template_doc(data, ws, PRESETS[name]); await db.templates.insert_one(doc); return clean(doc)

@api.get("/templates/{template_id}")
async def get_template(template_id: str, user=Depends(current_user)):
    ws = await active_workspace(user)
    doc = await db.templates.find_one({"id":template_id, "workspace_id":ws["id"]},{"_id":0}) if ws else None
    if not doc: raise HTTPException(404, "Template not found")
    return doc

@api.patch("/templates/{template_id}")
async def update_template(template_id: str, data: TemplateIn, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    doc = await db.templates.find_one({"id":template_id, "workspace_id":ws["id"]},{"_id":0})
    if not doc: raise HTTPException(404, "Template not found")
    questions=[{**q.model_dump(),"id":doc["questions"][i]["id"] if i<len(doc["questions"]) else str(uuid.uuid4()),"sort_order":i} for i,q in enumerate(data.questions)]
    await db.templates.update_one({"id":template_id},{"$set":{"name":data.name,"description":data.description,"questions":questions,"location_id":data.location_id,"updated_at":now()}})
    return await db.templates.find_one({"id":template_id},{"_id":0})

@api.delete("/templates/{template_id}")
async def delete_template(template_id: str, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    result = await db.templates.delete_one({"id":template_id, "workspace_id":ws["id"]})
    if result.deleted_count == 0: raise HTTPException(404, "Template not found")
    return {"ok":True}

@api.post("/templates/{template_id}/publish")
async def publish(template_id: str, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    doc = await db.templates.find_one({"id":template_id, "workspace_id":ws["id"]},{"_id":0})
    if not doc: raise HTTPException(404, "Template not found")
    if not doc["name"] or not doc["questions"]: raise HTTPException(400, "Add a name and at least one question before publishing")
    slug = doc.get("public_slug") or f"{secrets.token_urlsafe(5).lower()}-{secrets.token_urlsafe(4).lower()}"
    await db.templates.update_one({"id":template_id},{"$set":{"status":"PUBLISHED","public_slug":slug,"published_at":now()}})
    return {**doc,"status":"PUBLISHED","public_slug":slug,"published_at":now()}

# ---------- Public feedback ----------
@api.get("/public/feedback/{slug}")
async def public_feedback(slug: str):
    doc = await db.templates.find_one({"public_slug":slug, "status":"PUBLISHED"},{"_id":0})
    if not doc: raise HTTPException(404, "This feedback page is no longer available")
    ws = await db.workspaces.find_one({"id":doc["workspace_id"]},{"_id":0})
    loc = await db.locations.find_one({"id":doc.get("location_id")},{"_id":0}) if doc.get("location_id") else None
    return {"template":doc, "business":ws, "location":loc}

async def analyze_sentiment(response_id: str, workspace_id: str, comment: str):
    """Analyze text with Emergent LLM and store sentiment on the response."""
    if not comment or not comment.strip() or not EMERGENT_LLM_KEY: return
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system = ('You classify customer feedback. Respond ONLY with a compact JSON object: '
                  '{"sentiment":"positive"|"neutral"|"negative","confidence":0..1,"summary":"short one-line summary","topics":["topic1","topic2"]}. '
                  'No prose, no code fence.')
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"sentiment-{response_id}", system_message=system).with_model("openai", "gpt-5.4")
        msg = UserMessage(text=f"Review:\n{comment}")
        raw = await chat.send_message(msg)
        text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        text = text.strip().strip("`")
        if text.startswith("json"): text = text[4:].strip()
        data = json.loads(text)
        sentiment = str(data.get("sentiment", "neutral")).lower()
        if sentiment not in ("positive", "neutral", "negative"): sentiment = "neutral"
        payload = {"sentiment": sentiment, "confidence": float(data.get("confidence", 0)), "summary": str(data.get("summary", ""))[:200], "topics": [str(t)[:40] for t in (data.get("topics") or [])][:5], "analyzed_at": now()}
        await db.responses.update_one({"id":response_id, "workspace_id":workspace_id}, {"$set":{"ai": payload}})
    except Exception as e:
        log.error(f"Sentiment analysis failed for {response_id}: {e}")
        await db.responses.update_one({"id":response_id}, {"$set":{"ai":{"sentiment":"unknown","error":str(e)[:120]}}})

@api.post("/public/feedback/{slug}/responses")
async def submit_feedback(slug: str, data: ResponseIn, background: BackgroundTasks):
    doc = await db.templates.find_one({"public_slug":slug, "status":"PUBLISHED"},{"_id":0})
    if not doc: raise HTTPException(404, "This feedback page is no longer available")
    qmap = {q["id"]:q for q in doc["questions"]}; answers=[]; comment_text=""
    for a in data.answers:
        if a.question_id not in qmap: raise HTTPException(400, "Invalid question")
        q = qmap[a.question_id]
        if q["required"] and (a.value is None or str(a.value).strip()==""): raise HTTPException(400, "Please complete all required questions")
        answers.append({"id":str(uuid.uuid4()),"question_id":a.question_id,"value":a.value})
        if q["question_type"] in ("longtext","shorttext") and isinstance(a.value, str) and a.value.strip():
            comment_text += a.value.strip() + " "
    response_doc = {"id":str(uuid.uuid4()),"workspace_id":doc["workspace_id"],"template_id":doc["id"],"location_id":doc.get("location_id"),"submitted_at":now(),"answers":answers,"ai":None}
    await db.responses.insert_one(response_doc)
    if comment_text.strip(): background.add_task(analyze_sentiment, response_doc["id"], doc["workspace_id"], comment_text.strip())
    return {"ok":True, "response_id": response_doc["id"]}

# ---------- Dashboard, responses, analytics ----------
@api.get("/dashboard/summary")
async def summary(user=Depends(current_user)):
    ws = await active_workspace(user)
    if not ws: return {"workspace":None,"templates":0,"published":0,"responses":0,"average_rating":0,"recent":[],"sentiment":{"positive":0,"neutral":0,"negative":0}}
    ts = await db.templates.find({"workspace_id":ws["id"]},{"_id":0}).to_list(500)
    rs = await db.responses.find({"workspace_id":ws["id"]},{"_id":0}).sort("submitted_at",-1).to_list(50)
    ratings=[]; sent={"positive":0,"neutral":0,"negative":0}
    for r in rs:
        for a in r["answers"]:
            q = next((q for t in ts for q in t["questions"] if q["id"]==a["question_id"]), None)
            if q and q["question_type"]=="rating":
                try: ratings.append(float(a["value"]))
                except (TypeError, ValueError): pass
        s = (r.get("ai") or {}).get("sentiment")
        if s in sent: sent[s] += 1
    return {"workspace":ws,"templates":len(ts),"published":sum(t["status"]=="PUBLISHED" for t in ts),"responses":len(rs),"average_rating":round(sum(ratings)/len(ratings),1) if ratings else 0,"recent":rs[:5],"sentiment":sent}

@api.get("/responses")
async def responses(user=Depends(current_user)):
    ws = await active_workspace(user)
    return [] if not ws else [clean(x) async for x in db.responses.find({"workspace_id":ws["id"]},{"_id":0}).sort("submitted_at",-1)]

@api.get("/responses/{response_id}")
async def response_detail(response_id: str, user=Depends(current_user)):
    ws = await active_workspace(user)
    if not ws: raise HTTPException(404, "Response not found")
    r = await db.responses.find_one({"id":response_id, "workspace_id":ws["id"]},{"_id":0})
    if not r: raise HTTPException(404, "Response not found")
    t = await db.templates.find_one({"id":r["template_id"]},{"_id":0})
    loc = await db.locations.find_one({"id":r.get("location_id")},{"_id":0}) if r.get("location_id") else None
    return {"response":r, "template":t, "location":loc}

@api.post("/responses/{response_id}/reanalyze")
async def reanalyze(response_id: str, background: BackgroundTasks, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    r = await db.responses.find_one({"id":response_id, "workspace_id":ws["id"]},{"_id":0})
    if not r: raise HTTPException(404, "Response not found")
    t = await db.templates.find_one({"id":r["template_id"]},{"_id":0})
    text = ""
    if t:
        qmap = {q["id"]:q for q in t["questions"]}
        for a in r["answers"]:
            q = qmap.get(a["question_id"])
            if q and q["question_type"] in ("longtext","shorttext") and isinstance(a["value"], str):
                text += a["value"] + " "
    if text.strip(): background.add_task(analyze_sentiment, response_id, ws["id"], text.strip())
    return {"ok":True}

@api.get("/analytics")
async def analytics(user=Depends(current_user)):
    ws = await active_workspace(user)
    rs = [] if not ws else await db.responses.find({"workspace_id":ws["id"]},{"_id":0}).to_list(2000)
    dist = {str(i):0 for i in range(1,6)}; ratings=[]; sent={"positive":0,"neutral":0,"negative":0}
    topics_count = {}
    for r in rs:
        for a in r["answers"]:
            try:
                n = int(a["value"])
                if 1<=n<=5: dist[str(n)]+=1; ratings.append(n)
            except (TypeError, ValueError): pass
        ai = r.get("ai") or {}
        s = ai.get("sentiment")
        if s in sent: sent[s] += 1
        for topic in (ai.get("topics") or []):
            topics_count[topic] = topics_count.get(topic, 0) + 1
    top_topics = sorted(topics_count.items(), key=lambda x:-x[1])[:6]
    return {"total":len(rs),"distribution":dist,"average":round(sum(ratings)/len(ratings),1) if ratings else 0,"sentiment":sent,"topics":[{"name":k,"count":v} for k,v in top_topics]}

# ---------- Locations ----------
@api.get("/locations")
async def list_locations(user=Depends(current_user)):
    ws = await active_workspace(user)
    return [] if not ws else [clean(x) async for x in db.locations.find({"workspace_id":ws["id"]},{"_id":0}).sort("created_at",1)]

@api.post("/locations")
async def create_location(data: LocationIn, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    doc = {"id":str(uuid.uuid4()),"workspace_id":ws["id"],**data.model_dump(),"created_at":now()}
    await db.locations.insert_one(doc); return clean(doc)

@api.patch("/locations/{loc_id}")
async def update_location(loc_id: str, data: LocationIn, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner", "editor")
    result = await db.locations.update_one({"id":loc_id,"workspace_id":ws["id"]},{"$set":data.model_dump()})
    if result.matched_count == 0: raise HTTPException(404, "Location not found")
    return clean(await db.locations.find_one({"id":loc_id},{"_id":0}))

@api.delete("/locations/{loc_id}")
async def delete_location(loc_id: str, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner")
    result = await db.locations.delete_one({"id":loc_id,"workspace_id":ws["id"]})
    if result.deleted_count == 0: raise HTTPException(404, "Location not found")
    await db.templates.update_many({"workspace_id":ws["id"],"location_id":loc_id},{"$set":{"location_id":None}})
    return {"ok":True}

# ---------- Team members ----------
async def member_user(m):
    u = await db.users.find_one({"id":m.get("user_id")},{"_id":0,"password_hash":0}) if m.get("user_id") else None
    return {**m, "user": u}

@api.get("/team/members")
async def team_members(user=Depends(current_user)):
    ws = await active_workspace(user)
    if not ws: return {"owner":None, "members":[], "invites":[]}
    owner = await db.users.find_one({"id":ws["owner_id"]},{"_id":0,"password_hash":0})
    members = []; invites = []
    async for m in db.workspace_members.find({"workspace_id":ws["id"]},{"_id":0}):
        enriched = await member_user(m)
        (members if m["status"]=="active" else invites).append(enriched)
    return {"owner":owner, "members":members, "invites":invites, "role":ws.get("role")}

@api.post("/team/invites")
async def create_invite(data: InviteIn, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner")
    email = data.email.lower()
    if email == user["email"]: raise HTTPException(400, "You're already the owner")
    existing = await db.workspace_members.find_one({"workspace_id":ws["id"],"invite_email":email})
    if existing: raise HTTPException(409, "This email is already invited")
    invited_user = await db.users.find_one({"email":email},{"_id":0,"password_hash":0})
    tok = secrets.token_urlsafe(24)
    doc = {"id":str(uuid.uuid4()),"workspace_id":ws["id"],"invite_email":email,"role":data.role,"status":"pending","token":tok,"user_id":invited_user["id"] if invited_user else None,"invited_by":user["id"],"created_at":now()}
    await db.workspace_members.insert_one(doc)
    link = f"{APP_BASE_URL}/invite/{tok}" if APP_BASE_URL else f"/invite/{tok}"
    html = (f"<div style='font-family:Manrope,Arial,sans-serif;max-width:520px;margin:auto;padding:24px'>"
            f"<h2 style='color:#17352d;margin:0 0 8px'>You're invited to {ws['name']}</h2>"
            f"<p style='color:#5a6e68;font-size:14px;line-height:1.6'>{user['full_name']} invited you to help collect and read customer feedback as a <b>{data.role}</b>.</p>"
            f"<p style='margin:24px 0'><a href='{link}' style='background:#17352d;color:#fff;padding:12px 20px;border-radius:7px;text-decoration:none;font-weight:800;font-size:13px'>Accept invitation</a></p>"
            f"<p style='color:#9aa9a3;font-size:11px'>If the button doesn't work, open this link:<br>{link}</p></div>")
    sent = await send_email(email, f"Join {ws['name']} on feedback/loop", html)
    return {**clean(doc), "link": link, "email_sent": sent}

@api.get("/team/invites/{tok}")
async def view_invite(tok: str):
    inv = await db.workspace_members.find_one({"token":tok, "status":"pending"},{"_id":0})
    if not inv: raise HTTPException(404, "Invitation is invalid or has already been used")
    ws = await db.workspaces.find_one({"id":inv["workspace_id"]},{"_id":0,"owner_id":0})
    return {"invite":{"email":inv["invite_email"],"role":inv["role"]}, "workspace":ws}

@api.post("/team/invites/{tok}/accept")
async def accept_invite(tok: str, user=Depends(current_user)):
    inv = await db.workspace_members.find_one({"token":tok, "status":"pending"},{"_id":0})
    if not inv: raise HTTPException(404, "Invitation is invalid or has already been used")
    if inv["invite_email"] != user["email"]: raise HTTPException(403, "This invitation was sent to a different email")
    await db.workspace_members.update_one({"id":inv["id"]},{"$set":{"status":"active","user_id":user["id"],"token":"","accepted_at":now()}})
    return {"ok":True, "workspace_id":inv["workspace_id"]}

@api.patch("/team/members/{member_id}")
async def update_member(member_id: str, data: RoleUpdateIn, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner")
    result = await db.workspace_members.update_one({"id":member_id,"workspace_id":ws["id"]},{"$set":{"role":data.role}})
    if result.matched_count == 0: raise HTTPException(404, "Member not found")
    return {"ok":True}

@api.delete("/team/members/{member_id}")
async def remove_member(member_id: str, user=Depends(current_user)):
    ws = await active_workspace(user); require_role(ws, "owner")
    result = await db.workspace_members.delete_one({"id":member_id,"workspace_id":ws["id"]})
    if result.deleted_count == 0: raise HTTPException(404, "Member not found")
    return {"ok":True}

# ---------- App setup ----------
app.include_router(api)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS","*").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
@app.get("/")
async def root(): return {"message":"Customer Feedback Platform API"}
@app.on_event("startup")
async def indexes():
    await db.users.create_index("email", unique=True)
    await db.templates.create_index("public_slug", unique=True, sparse=True)
    await db.login_attempts.create_index("identifier")
    await db.workspace_members.create_index("token", sparse=True)
    await db.workspace_members.create_index([("workspace_id",1),("invite_email",1)])
    await db.responses.create_index([("workspace_id",1),("submitted_at",-1)])
    await db.locations.create_index("workspace_id")
@app.on_event("shutdown")
async def shutdown(): client.close()

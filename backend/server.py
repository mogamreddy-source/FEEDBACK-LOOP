from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import Any, List, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os, uuid, secrets, bcrypt, jwt, logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Customer Feedback Platform API")
api = APIRouter(prefix="/api")
JWT_SECRET = os.environ["JWT_SECRET"]

def now(): return datetime.now(timezone.utc).isoformat()
def clean(doc):
    if not doc: return None
    doc = dict(doc); doc.pop("_id", None)
    return doc
def hash_password(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def verify_password(password, hashed): return bcrypt.checkpw(password.encode(), hashed.encode())
def token(user_id): return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc)+timedelta(days=7), "type":"access"}, JWT_SECRET, algorithm="HS256")

class RegisterIn(BaseModel): full_name: str = Field(min_length=2); email: EmailStr; password: str = Field(min_length=8)
class LoginIn(BaseModel): email: EmailStr; password: str
class WorkspaceIn(BaseModel): name: str = Field(min_length=2); business_type: str = "Other"; logo_url: str = ""; website: str = ""; location: str = ""; description: str = ""
class QuestionIn(BaseModel): question_text: str; question_type: str = "rating"; required: bool = True; description: str = ""; options: List[str] = []
class TemplateIn(BaseModel): name: str; description: str = ""; questions: List[QuestionIn] = []
class AnswerIn(BaseModel): question_id: str; value: Any
class ResponseIn(BaseModel): answers: List[AnswerIn]

async def current_user(request: Request):
    raw = request.headers.get("Authorization", "").replace("Bearer ", "") or request.cookies.get("access_token")
    if not raw: raise HTTPException(401, "Please sign in to continue")
    try: payload = jwt.decode(raw, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(401, "Your session has expired")
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id":0, "password_hash":0})
    if not user: raise HTTPException(401, "User not found")
    return user
async def owned_workspace(user):
    ws = await db.workspaces.find_one({"owner_id": user["id"]}, {"_id":0})
    return ws

@api.post("/auth/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}): raise HTTPException(409, "An account with this email already exists")
    user = {"id":str(uuid.uuid4()), "full_name":data.full_name, "email":email, "password_hash":hash_password(data.password), "created_at":now()}
    await db.users.insert_one(user)
    access = token(user["id"]); response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=604800)
    return {"user": {k:v for k,v in user.items() if k not in ("password_hash", "_id")}, "access_token":access}

@api.post("/auth/login")
async def login(data: LoginIn, response: Response, request: Request):
    identifier = data.email.lower()
    attempt = await db.login_attempts.find_one({"identifier":identifier}, {"_id":0})
    if attempt and attempt.get("locked_until", "") > now(): raise HTTPException(429, "Too many attempts. Please try again in 15 minutes")
    user = await db.users.find_one({"email":data.email.lower()})
    if not user or not verify_password(data.password, user["password_hash"]):
        count=(attempt.get("count",0) if attempt else 0)+1
        await db.login_attempts.update_one({"identifier":identifier},{"$set":{"identifier":identifier,"count":count,"locked_until":(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat() if count>=5 else ""}},upsert=True)
        raise HTTPException(401, "Incorrect email or password")
    await db.login_attempts.delete_one({"identifier":identifier})
    access = token(user["id"]); response.set_cookie("access_token", access, httponly=True, samesite="lax", max_age=604800)
    return {"user": {k:v for k,v in user.items() if k not in ("password_hash","_id")}, "access_token":access}

@api.post("/auth/logout")
async def logout(response: Response): response.delete_cookie("access_token"); return {"ok":True}
@api.get("/auth/me")
async def me(user=Depends(current_user)): return user

@api.get("/workspaces")
async def workspaces(user=Depends(current_user)): return [clean(x) async for x in db.workspaces.find({"owner_id":user["id"]}, {"_id":0})]
@api.post("/workspaces")
async def create_workspace(data: WorkspaceIn, user=Depends(current_user)):
    ws = {"id":str(uuid.uuid4()), "owner_id":user["id"], **data.model_dump(), "created_at":now()}; await db.workspaces.insert_one(ws); return clean(ws)

PRESETS = {
 "Restaurant Experience":[("How would you rate your overall experience?","rating"),("How would you rate the food quality?","rating"),("How would you rate our service?","rating"),("Would you recommend us?","yesno"),("Tell us more about your experience.","longtext")],
 "Product Purchase":[("How would you rate your purchase?","rating"),("Did the product meet your expectations?","yesno"),("What could we improve?","longtext")],
 "Service Experience":[("How would you rate our service?","rating"),("Was your issue resolved?","yesno"),("Share any additional feedback.","longtext")],
 "General Customer Feedback":[("How was your overall experience?","rating"),("Would you recommend us?","yesno"),("Tell us more.","longtext")]
}
def template_doc(data, user, ws, preset=None):
    questions=[]
    source = preset or [(q.question_text,q.question_type) for q in data.questions]
    for i,(text,typ) in enumerate(source): questions.append({"id":str(uuid.uuid4()),"question_text":text,"question_type":typ,"required":True,"description":"","options":["Yes","No"] if typ=="yesno" else [],"sort_order":i})
    return {"id":str(uuid.uuid4()),"workspace_id":ws["id"],"name":data.name,"description":data.description,"status":"DRAFT","public_slug":"","published_at":None,"questions":questions,"created_at":now(),"updated_at":now()}

@api.get("/templates")
async def templates(user=Depends(current_user)):
    ws=await owned_workspace(user); return [] if not ws else [clean(x) async for x in db.templates.find({"workspace_id":ws["id"]},{"_id":0})]
@api.get("/templates/presets")
async def presets(user=Depends(current_user)): return [{"name":k,"question_count":len(v),"questions":[q[0] for q in v]} for k,v in PRESETS.items()]
@api.post("/templates")
async def create_template(data: TemplateIn, user=Depends(current_user)):
    ws=await owned_workspace(user)
    if not ws: raise HTTPException(400,"Create your business first")
    doc=template_doc(data,user,ws); await db.templates.insert_one(doc); return clean(doc)
@api.post("/templates/from-preset/{name}")
async def create_preset(name: str, user=Depends(current_user)):
    ws=await owned_workspace(user)
    if name not in PRESETS or not ws: raise HTTPException(404,"Template preset not found")
    data=TemplateIn(name=name,description="A ready-to-use feedback form."); doc=template_doc(data,user,ws,PRESETS[name]); await db.templates.insert_one(doc); return clean(doc)
@api.get("/templates/{template_id}")
async def get_template(template_id: str, user=Depends(current_user)):
    ws=await owned_workspace(user); doc=await db.templates.find_one({"id":template_id,"workspace_id":ws["id"]},{"_id":0}) if ws else None
    if not doc: raise HTTPException(404,"Template not found")
    return doc
@api.patch("/templates/{template_id}")
async def update_template(template_id: str, data: TemplateIn, user=Depends(current_user)):
    ws=await owned_workspace(user); doc=await db.templates.find_one({"id":template_id,"workspace_id":ws["id"]},{"_id":0}) if ws else None
    if not doc: raise HTTPException(404,"Template not found")
    questions=[{**q.model_dump(),"id":doc["questions"][i]["id"] if i<len(doc["questions"]) else str(uuid.uuid4()),"sort_order":i} for i,q in enumerate(data.questions)]
    await db.templates.update_one({"id":template_id},{"$set":{"name":data.name,"description":data.description,"questions":questions,"updated_at":now()}})
    return await db.templates.find_one({"id":template_id},{"_id":0})
@api.delete("/templates/{template_id}")
async def delete_template(template_id: str,user=Depends(current_user)):
    ws=await owned_workspace(user); result=await db.templates.delete_one({"id":template_id,"workspace_id":ws["id"]}) if ws else None
    if not result or result.deleted_count==0: raise HTTPException(404,"Template not found")
    return {"ok":True}
@api.post("/templates/{template_id}/publish")
async def publish(template_id: str,user=Depends(current_user)):
    ws=await owned_workspace(user); doc=await db.templates.find_one({"id":template_id,"workspace_id":ws["id"]},{"_id":0}) if ws else None
    if not doc: raise HTTPException(404,"Template not found")
    if not doc["name"] or not doc["questions"]: raise HTTPException(400,"Add a name and at least one question before publishing")
    slug=doc.get("public_slug") or f"{secrets.token_urlsafe(5).lower()}-{secrets.token_urlsafe(4).lower()}"
    await db.templates.update_one({"id":template_id},{"$set":{"status":"PUBLISHED","public_slug":slug,"published_at":now()}})
    return {**doc,"status":"PUBLISHED","public_slug":slug,"published_at":now()}

@api.get("/public/feedback/{slug}")
async def public_feedback(slug:str):
    doc=await db.templates.find_one({"public_slug":slug,"status":"PUBLISHED"},{"_id":0})
    if not doc: raise HTTPException(404,"This feedback page is no longer available")
    ws=await db.workspaces.find_one({"id":doc["workspace_id"]},{"_id":0})
    return {"template":doc,"business":ws}
@api.post("/public/feedback/{slug}/responses")
async def submit_feedback(slug:str,data:ResponseIn):
    doc=await db.templates.find_one({"public_slug":slug,"status":"PUBLISHED"},{"_id":0})
    if not doc: raise HTTPException(404,"This feedback page is no longer available")
    qmap={q["id"]:q for q in doc["questions"]}; answers=[]
    for answer in data.answers:
        if answer.question_id not in qmap: raise HTTPException(400,"Invalid question")
        if qmap[answer.question_id]["required"] and (answer.value is None or str(answer.value).strip()==""): raise HTTPException(400,"Please complete all required questions")
        answers.append({"id":str(uuid.uuid4()),"question_id":answer.question_id,"value":answer.value})
    response_doc={"id":str(uuid.uuid4()),"workspace_id":doc["workspace_id"],"template_id":doc["id"],"submitted_at":now(),"answers":answers}
    await db.responses.insert_one(response_doc); return {"ok":True}

@api.get("/dashboard/summary")
async def summary(user=Depends(current_user)):
    ws=await owned_workspace(user)
    if not ws: return {"workspace":None,"templates":0,"published":0,"responses":0,"average_rating":0,"recent":[]}
    ts=await db.templates.find({"workspace_id":ws["id"]},{"_id":0}).to_list(500); rs=await db.responses.find({"workspace_id":ws["id"]},{"_id":0}).sort("submitted_at",-1).to_list(50)
    ratings=[]
    for r in rs:
        for a in r["answers"]:
            q=next((q for t in ts for q in t["questions"] if q["id"]==a["question_id"]),None)
            if q and q["question_type"]=="rating": ratings.append(float(a["value"]))
    return {"workspace":ws,"templates":len(ts),"published":sum(t["status"]=="PUBLISHED" for t in ts),"responses":len(rs),"average_rating":round(sum(ratings)/len(ratings),1) if ratings else 0,"recent":rs[:5]}
@api.get("/responses")
async def responses(user=Depends(current_user)):
    ws=await owned_workspace(user); return [] if not ws else [clean(x) async for x in db.responses.find({"workspace_id":ws["id"]},{"_id":0}).sort("submitted_at",-1)]
@api.get("/analytics")
async def analytics(user=Depends(current_user)):
    ws=await owned_workspace(user); rs=[] if not ws else await db.responses.find({"workspace_id":ws["id"]},{"_id":0}).to_list(500); dist={str(i):0 for i in range(1,6)}
    ratings=[]
    for r in rs:
        for a in r["answers"]:
            try:
                n=int(a["value"])
                if 1<=n<=5: dist[str(n)]+=1; ratings.append(n)
            except (TypeError, ValueError): pass
    return {"total":len(rs),"distribution":dist,"average":round(sum(ratings)/len(ratings),1) if ratings else 0}

app.include_router(api)
app.add_middleware(CORSMiddleware,allow_origins=os.environ.get("CORS_ORIGINS","*").split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.get("/")
async def root(): return {"message":"Customer Feedback Platform API"}
@app.on_event("startup")
async def indexes(): await db.users.create_index("email",unique=True); await db.templates.create_index("public_slug",unique=True,sparse=True); await db.login_attempts.create_index("identifier")
@app.on_event("shutdown")
async def shutdown(): client.close()
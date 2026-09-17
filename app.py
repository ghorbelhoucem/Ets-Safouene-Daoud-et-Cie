import os, hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, Boolean, DateTime, ForeignKey, Text, select, func, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

url=os.getenv("DATABASE_URL","sqlite:///./supply.db")
if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
engine=create_engine(url,pool_pre_ping=True,connect_args={"check_same_thread":False} if url.startswith("sqlite") else {})
SECRET=os.getenv("JWT_SECRET",secrets.token_hex(32))

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(100),unique=True)
    pin_hash:Mapped[str]=mapped_column(String(200)); role:Mapped[str]=mapped_column(String(20),default="employee"); active:Mapped[bool]=mapped_column(Boolean,default=True)
class Item(Base):
    __tablename__="items"; id:Mapped[int]=mapped_column(primary_key=True); sku:Mapped[str]=mapped_column(String(80),unique=True); name:Mapped[str]=mapped_column(String(160))
    kind:Mapped[str]=mapped_column(String(20)); category:Mapped[str]=mapped_column(String(100),default=""); location:Mapped[str]=mapped_column(String(100),default="")
    quantity:Mapped[int]=mapped_column(Integer,default=0); min_stock:Mapped[int]=mapped_column(Integer,default=0); unit:Mapped[str]=mapped_column(String(30),default="pcs")
    notes:Mapped[str]=mapped_column(Text,default=""); active:Mapped[bool]=mapped_column(Boolean,default=True)
class Loan(Base):
    __tablename__="loans"; id:Mapped[int]=mapped_column(primary_key=True); item_id:Mapped[int]=mapped_column(ForeignKey("items.id")); user_id:Mapped[int]=mapped_column(ForeignKey("users.id"))
    checked_out_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow); returned_at:Mapped[Optional[datetime]]=mapped_column(DateTime,nullable=True); note:Mapped[str]=mapped_column(Text,default="")
class Movement(Base):
    __tablename__="movements"; id:Mapped[int]=mapped_column(primary_key=True); item_id:Mapped[Optional[int]]=mapped_column(ForeignKey("items.id"),nullable=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id")); action:Mapped[str]=mapped_column(String(40)); quantity:Mapped[int]=mapped_column(Integer,default=0)
    note:Mapped[str]=mapped_column(Text,default=""); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)

def db():
    with Session(engine) as s: yield s
def ph(pin):
    salt=secrets.token_hex(16); d=hashlib.pbkdf2_hmac("sha256",pin.encode(),bytes.fromhex(salt),120000).hex(); return salt+"$"+d
def pv(pin,stored):
    try:
        salt,d=stored.split("$",1); t=hashlib.pbkdf2_hmac("sha256",pin.encode(),bytes.fromhex(salt),120000).hex(); return hmac.compare_digest(t,d)
    except:return False
def seed():
    if os.getenv("SEED_DEMO","true").lower()!="true": return
    with Session(engine) as s:
        if not s.scalar(select(func.count(User.id))):
            s.add_all([User(name="Majdi",pin_hash=ph("1234")),User(name="Admin",pin_hash=ph("2026"),role="admin")])
        if not s.scalar(select(func.count(Item.id))):
            s.add_all([Item(sku="KIA-OIL-5W30",name="Engine Oil 5W-30",kind="part",category="Lubricants",location="A-01",quantity=24,min_stock=10,unit="L"),
            Item(sku="KIA-FILTER-OIL",name="Oil Filter",kind="part",category="Filters",location="A-02",quantity=18,min_stock=8),
            Item(sku="KIA-FILTER-AIR",name="Air Filter",kind="part",category="Filters",location="A-03",quantity=6,min_stock=8),
            Item(sku="TOOL-TORQUE-01",name="Torque Wrench",kind="tool",category="Hand Tools",location="T-01",quantity=1),
            Item(sku="TOOL-DIAG-01",name="Diagnostic Scanner",kind="tool",category="Diagnostics",location="T-02",quantity=1)])
        s.commit()
seed()

app=FastAPI(title="ETS Safouene Daoud et Cie Supply Room"); app.mount("/static",StaticFiles(directory="static"),name="static")
class Login(BaseModel): name:str; pin:str
class ItemIn(BaseModel): sku:str; name:str; kind:str; category:str=""; location:str=""; quantity:int=0; min_stock:int=0; unit:str="pcs"; notes:str=""
class Qty(BaseModel): quantity:int=Field(gt=0); note:str=""
class LoanIn(BaseModel): user_id:Optional[int]=None; note:str=""
class UserIn(BaseModel): name:str; pin:str=Field(min_length=4); role:str="employee"

def auth(authorization:Optional[str]=Header(None),s:Session=Depends(db)):
    if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"Login required")
    try:
        p=jwt.decode(authorization[7:],SECRET,algorithms=["HS256"]); u=s.get(User,int(p["sub"]))
        if not u or not u.active: raise ValueError()
        return u
    except: raise HTTPException(401,"Invalid session")
def adm(u:User=Depends(auth)):
    if u.role!="admin": raise HTTPException(403,"Admin access required")
    return u
def ij(i,s):
    l=s.scalar(select(Loan).where(Loan.item_id==i.id,Loan.returned_at.is_(None)).order_by(Loan.id.desc()))
    holder=s.get(User,l.user_id).name if l else None
    return {k:getattr(i,k) for k in ["id","sku","name","kind","category","location","quantity","min_stock","unit","notes","active"]}|{"low_stock":i.kind=="part" and i.quantity<=i.min_stock,"checked_out":bool(l),"holder":holder}

@app.get("/")
def root(): return FileResponse("static/index.html")
@app.get("/health")
def health(): return {"ok":True}
@app.post("/api/login")
def login(x:Login,s:Session=Depends(db)):
    u=s.scalar(select(User).where(func.lower(User.name)==x.name.lower(),User.active==True))
    if not u or not pv(x.pin,u.pin_hash): raise HTTPException(401,"Incorrect name or PIN")
    t=jwt.encode({"sub":str(u.id),"exp":datetime.now(timezone.utc)+timedelta(hours=12)},SECRET,algorithm="HS256")
    return {"token":t,"user":{"id":u.id,"name":u.name,"role":u.role}}
@app.get("/api/me")
def me(u=Depends(auth)): return {"id":u.id,"name":u.name,"role":u.role}
@app.get("/api/dashboard")
def dashboard(u=Depends(auth),s:Session=Depends(db)):
    p=s.scalars(select(Item).where(Item.active==True,Item.kind=="part")).all(); t=s.scalars(select(Item).where(Item.active==True,Item.kind=="tool")).all()
    return {"parts":len(p),"tools":len(t),"units":sum(x.quantity for x in p),"low_stock":sum(x.quantity<=x.min_stock for x in p),"open_loans":s.scalar(select(func.count(Loan.id)).where(Loan.returned_at.is_(None))) or 0}
@app.get("/api/items")
def items(kind:Optional[str]=None,q:Optional[str]=None,u=Depends(auth),s:Session=Depends(db)):
    st=select(Item).where(Item.active==True)
    if kind: st=st.where(Item.kind==kind)
    if q:
        z=f"%{q}%"; st=st.where(or_(Item.name.ilike(z),Item.sku.ilike(z),Item.category.ilike(z),Item.location.ilike(z)))
    return [ij(i,s) for i in s.scalars(st.order_by(Item.name)).all()]
@app.post("/api/items")
def add_item(x:ItemIn,u=Depends(adm),s:Session=Depends(db)):
    if x.kind not in ("part","tool"): raise HTTPException(400,"Invalid item type")
    if s.scalar(select(Item).where(Item.sku==x.sku)): raise HTTPException(409,"SKU already exists")
    i=Item(**x.model_dump());s.add(i);s.flush();s.add(Movement(item_id=i.id,user_id=u.id,action="create",quantity=i.quantity,note="Item created"));s.commit();return ij(i,s)
@app.put("/api/items/{iid}")
def edit(iid:int,x:ItemIn,u=Depends(adm),s:Session=Depends(db)):
    i=s.get(Item,iid)
    if not i: raise HTTPException(404)
    old=i.quantity
    for k,v in x.model_dump().items():setattr(i,k,v)
    s.add(Movement(item_id=i.id,user_id=u.id,action="edit",quantity=i.quantity-old,note="Item edited"));s.commit();return ij(i,s)
@app.delete("/api/items/{iid}")
def archive(iid:int,u=Depends(adm),s:Session=Depends(db)):
    i=s.get(Item,iid)
    if not i:raise HTTPException(404)
    i.active=False;s.add(Movement(item_id=i.id,user_id=u.id,action="archive",note="Item archived"));s.commit();return {"ok":True}
@app.post("/api/items/{iid}/{action}")
def stock(iid:int,action:str,x:Qty,u=Depends(auth),s:Session=Depends(db)):
    if action not in ("consume","restock"):raise HTTPException(404)
    i=s.get(Item,iid)
    if not i or i.kind!="part":raise HTTPException(404)
    delta=-x.quantity if action=="consume" else x.quantity
    if i.quantity+delta<0:raise HTTPException(400,"Not enough stock")
    i.quantity+=delta;s.add(Movement(item_id=i.id,user_id=u.id,action=action,quantity=delta,note=x.note));s.commit();return ij(i,s)
@app.post("/api/tools/{iid}/checkout")
def checkout(iid:int,x:LoanIn,u=Depends(auth),s:Session=Depends(db)):
    i=s.get(Item,iid)
    if not i or i.kind!="tool":raise HTTPException(404)
    if s.scalar(select(Loan).where(Loan.item_id==iid,Loan.returned_at.is_(None))):raise HTTPException(409,"Tool already checked out")
    b=s.get(User,x.user_id) if x.user_id else u
    if not b or not b.active:raise HTTPException(400,"Invalid employee")
    s.add(Loan(item_id=iid,user_id=b.id,note=x.note));s.add(Movement(item_id=iid,user_id=u.id,action="checkout",note=f"To {b.name}. {x.note}"));s.commit();return ij(i,s)
@app.post("/api/tools/{iid}/return")
def ret(iid:int,x:LoanIn,u=Depends(auth),s:Session=Depends(db)):
    l=s.scalar(select(Loan).where(Loan.item_id==iid,Loan.returned_at.is_(None)).order_by(Loan.id.desc()))
    if not l:raise HTTPException(404,"No active checkout")
    l.returned_at=datetime.utcnow();s.add(Movement(item_id=iid,user_id=u.id,action="return",note=x.note));s.commit();return ij(s.get(Item,iid),s)
@app.get("/api/history")
def history(u=Depends(auth),s:Session=Depends(db)):
    out=[]
    for m in s.scalars(select(Movement).order_by(Movement.id.desc()).limit(500)).all():
        i=s.get(Item,m.item_id) if m.item_id else None;a=s.get(User,m.user_id)
        out.append({"time":m.created_at.isoformat(),"action":m.action,"quantity":m.quantity,"note":m.note,"item":i.name if i else "—","sku":i.sku if i else "—","user":a.name if a else "—"})
    return out
@app.get("/api/users")
def users(u=Depends(auth),s:Session=Depends(db)):return [{"id":x.id,"name":x.name,"role":x.role} for x in s.scalars(select(User).where(User.active==True).order_by(User.name)).all()]
@app.post("/api/users")
def add_user(x:UserIn,u=Depends(adm),s:Session=Depends(db)):
    if x.role not in ("employee","admin"):raise HTTPException(400,"Invalid role")
    if s.scalar(select(User).where(func.lower(User.name)==x.name.lower())):raise HTTPException(409,"Employee already exists")
    n=User(name=x.name,pin_hash=ph(x.pin),role=x.role);s.add(n);s.commit();return {"id":n.id,"name":n.name,"role":n.role}
@app.delete("/api/users/{uid}")
def del_user(uid:int,u=Depends(adm),s:Session=Depends(db)):
    if uid==u.id:raise HTTPException(400,"Cannot disable yourself")
    t=s.get(User,uid)
    if not t:raise HTTPException(404)
    t.active=False;s.commit();return {"ok":True}

import sys, os, types, enum, json, re, inspect, asyncio, contextlib
import pathlib; _here=pathlib.Path(__file__).resolve().parent; sys.path.insert(0,str(_here)); sys.path.insert(0,str(_here.parent.parent))
os.environ.update(WZ_SQLITE_PATH=":memory:", WZ_JWT_SECRET="x"*40)
# fake DB layer (SQLAlchemy not installed)
class RoleEnum(enum.Enum): caregiver="caregiver"; administrator="administrator"
class _Q:
    def filter_by(s,**k): return s
    def order_by(s,*a): return s
    def all(s): return []
    def first(s): return None
class _Col:
    def __getattr__(s,n): return n
class User: full_name=_Col(); 
class Patient: full_name="full_name"
class PatientProfile: pass
class SensorDevice: pass
class _DB:
    def query(s,*a): return _Q()
    def get(s,*a): return None
@contextlib.contextmanager
def get_session(): yield _DB()
for name,attrs in {"database.session":dict(get_session=get_session,init_db=lambda *a:None),
  "database.models":dict(User=User,RoleEnum=RoleEnum,Patient=Patient,PatientProfile=PatientProfile,SensorDevice=SensorDevice),
  "database.seed":dict(seed=lambda *a,**k:None)}.items():
    m=types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name]=m
import fastapi
from fastapi import HTTPException, _Dep, _Hdr
import apps.api.main as main
app=main.app
def _resolve(fn, ctx):
    sig=inspect.signature(fn); kw={}
    for n,p in sig.parameters.items():
        d=p.default
        if isinstance(d,_Dep): kw[n]=_resolve(d.fn,ctx)()
        elif isinstance(d,_Hdr): kw[n]=ctx["headers"].get(n.replace("_","-").lower(),d.default)
    return lambda: fn(**kw)
def call(method,path,json_body=None,query=None,token=None):
    try: return _call(method,path,json_body,query,token)
    except HTTPException as e: return e.status_code,e.detail
def _call(method,path,json_body=None,query=None,token=None):
    for m,pat,rx,fn in app.routes:
        if m!=method: continue
        mt=rx.match(path)
        if not mt: continue
        ctx={"headers":{"authorization":f"Bearer {token}"} if token else {}}
        sig=inspect.signature(fn); kw={}; body=json_body or {}
        hints=fn.__annotations__
        simple_body=[n for n,p in sig.parameters.items() if n not in mt.groupdict() and not isinstance(p.default,(_Dep,_Hdr))]
        for n,p in sig.parameters.items():
            d=p.default; ann=str(hints.get(n,""))
            if isinstance(d,_Dep): kw[n]=_resolve(d.fn,ctx)()
            elif n in mt.groupdict(): kw[n]=int(mt[n]) if ann=="int" else mt[n]
            elif inspect.isclass(getattr(main,ann,None)) and issubclass(getattr(main,ann),__import__('pydantic').BaseModel):
                kw[n]=getattr(main,ann)(**body)
            elif ann.startswith(("dict","list")) and m=="POST":
                if n in body: kw[n]=body[n]
                elif d is not inspect._empty: kw[n]=d
                else: raise KeyError(f"422 missing body field {n}")
            else:
                q=(query or {})
                if n in q: kw[n]=q[n]
                elif d is not inspect._empty: kw[n]=d
        try: return 200, fn(**kw)
        except HTTPException as e: return e.status_code, e.detail
    return 404,"no route"

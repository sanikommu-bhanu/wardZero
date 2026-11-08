import re
class HTTPException(Exception):
    def __init__(self, status_code, detail=None): self.status_code=status_code; self.detail=detail
class _Dep:
    def __init__(self, fn): self.fn=fn
def Depends(fn): return _Dep(fn)
class _Hdr:
    def __init__(self, default=None): self.default=default
def Header(default=None): return _Hdr(default)
class status:
    HTTP_401_UNAUTHORIZED=401; HTTP_403_FORBIDDEN=403; HTTP_404_NOT_FOUND=404
class WebSocket: pass
class WebSocketDisconnect(Exception): pass
class FastAPI:
    def __init__(self,**kw): self.routes=[]; self.startup=[]; self.mw=[]
    def add_middleware(self,cls,**kw): self.mw.append((cls,kw))
    def on_event(self,ev):
        def d(f): self.startup.append(f); return f
        return d
    def _reg(self,method,path):
        def d(f):
            rx=re.compile("^"+re.sub(r"\{(\w+)\}",r"(?P<\1>[^/]+)",path)+"$")
            self.routes.append((method,path,rx,f)); return f
        return d
    def get(self,p,**k): return self._reg("GET",p)
    def post(self,p,**k): return self._reg("POST",p)
    def put(self,p,**k): return self._reg("PUT",p)
    def delete(self,p,**k): return self._reg("DELETE",p)
    def websocket(self,p,**k): return self._reg("WS",p)

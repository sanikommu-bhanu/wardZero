import re
class _F:
    def __init__(self,default=...,pattern=None,max_length=None,**k): self.default=default; self.pattern=pattern; self.max_length=max_length
def Field(default=...,**k): return _F(default,**k)
class ValidationError(Exception): pass
class BaseModel:
    def __init__(self,**kw):
        ann={}
        for c in reversed(type(self).__mro__): ann.update(getattr(c,"__annotations__",{}))
        for name in ann:
            dflt=getattr(type(self),name,...)
            f=dflt if isinstance(dflt,_F) else None
            d=f.default if f else dflt
            if name in kw: v=kw[name]
            elif d is not ...: v=d
            else: raise ValidationError(f"missing {name}")
            if f and f.pattern and isinstance(v,str) and not re.match(f.pattern,v): raise ValidationError(f"{name} pattern")
            setattr(self,name,v)

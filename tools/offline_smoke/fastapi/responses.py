class Response:
    def __init__(self,content=None,media_type=None,headers=None,status_code=200): self.content=content; self.media_type=media_type; self.headers=headers or {}; self.status_code=status_code
class JSONResponse(Response): pass
class StreamingResponse(Response): pass

from enum import Enum

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Response, status, Depends
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
from uuid import uuid4, UUID
from sqlalchemy.orm import Session

from vk import get_account_info, get_access_token, AccountInfo
from session import backend, cookie, verifier
from models import Code
from db import get_db

from python.handler import handler as py_handler
from kotlin.handler import handler as kt_handler
from c.handler import handler as c_handler
from go.handler import handler as go_handler
from java.handler import handler as java_handler
from javascript.handler import handler as js_handler

functions = {'python': ('ast', 'cfg'), 'kotlin': ('ast', 'cfg'), 'c': ('ast', 'cfg', 'ssa'), 'go': ('ast', 'cfg'),
             'java': ('ast', 'cfg'), 'javascript': ('ast',)}
handlers = {"python": py_handler, "kotlin": kt_handler, "c": c_handler, 'go': go_handler, 'java': java_handler,
            'javascript': js_handler}


class Format(str, Enum):
    png = 'image/png'
    svg = 'image/svg+xml'
    pdf = 'application/pdf'
    dot = 'text/dot'


example_code = """
a = 2 + 2 * (c * d / 2)
b = a + a / 2
if b > 4:
    print('hello')
else:
    print('nooo')
print('exit')
"""

app = FastAPI()
app.mount("/client", StaticFiles(directory="../client"), name="client")


@app.get("/")
async def root(request: Request):
    return FileResponse('../client/views/index.html')


@app.get("/vk", tags=['User'])
async def vk(code: str):
    code = get_access_token(code)
    if code is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Error')
    user = get_account_info(code)

    session = uuid4()

    await backend.create(session, user)
    res = RedirectResponse('/')
    cookie.attach_to_response(res, session)
    return res


@app.get("/whoami", dependencies=[Depends(cookie)], tags=['User'])
async def whoami(session_data: AccountInfo = Depends(verifier)):
    return session_data


@app.get("/exit", tags=['User'])
async def del_session(response: Response, session_id: UUID = Depends(cookie)):
    await backend.delete(session_id)
    cookie.delete_from_response(response)
    return "exit"


@app.post("/save", dependencies=[Depends(cookie)], tags=['User'])
async def save(language: str, code: str, session_data: AccountInfo = Depends(verifier), db: Session = Depends(get_db)):
    c = Code(language=language, code=code, user_id=session_data.id)
    try:
        db.add(c)
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return 'ok'


@app.get("/code", dependencies=[Depends(cookie)], tags=['User'])
async def code(session_data: AccountInfo = Depends(verifier), db: Session = Depends(get_db)):
    all_code = db.query(Code).filter(Code.user_id == session_data.id).all()
    print(all_code)
    return all_code




@app.get('/functions')
async def all_functions():
    """return all available languages and models"""
    return functions


@app.get('/view_graph')
async def view_graph(code: str = example_code, lang: str = "python", model: str = "ast"):
    if lang in functions and model in functions[lang]:
        try:
            data = handlers.get(lang)(code, model)
            return Response(data, media_type=f"text/dot")
        except SyntaxError as e:
            raise HTTPException(400, detail=str(e))
        except Exception as e:
            raise HTTPException(400, detail=str(e))
    else:
        raise HTTPException(400, "Language and model not implemented")


# @app.get('/python_ast', response_class=StreamingResponse)
# async def ast(format: Format, code: str = example_code):
#     data = python_ast.make(code, format=format.name)
#     return StreamingResponse(data, media_type=format.value)
#
#
# @app.get('/python_cfg')
# async def cfg(code: str = example_code):
#     data = python_cfg.make(code)
#     return StreamingResponse(data, media_type=f"text/dot")
#

# @app.get('/c_ssa', response_class=Response)
# async def c_ssa(code: str = c_handler_.example_code):
#     try:
#         data = c_handler_.handler(code, model='ssa')
#     except RuntimeError as e:
#         raise HTTPException(400, detail=str(e))
#     return Response(data, media_type=f"text/dot")
#
#
# @app.get('/c_cfg', response_class=Response)
# async def c_cfg(code: str = c_handler_.example_code):
#     try:
#         data = c_handler_.handler(code, model='cfg')
#     except RuntimeError as e:
#         raise HTTPException(400, detail=str(e))
#     return Response(data, media_type=f"text/dot")


if __name__ == '__main__':
    print(os.environ['client_id'])
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True, debug=True)

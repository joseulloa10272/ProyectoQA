from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List
import os
from Persistencia.usuarioPersistencia import obtenerTipoUsuario  

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Usuario(BaseModel):
    id: int
    nombreUsuario: str
    correo: str
    tipoUsuario: str
    contrasena: str

@app.post("/integrar_usuario", response_model=Usuario)
async def crear_usuario(usuario: Usuario, token: str = Depends(oauth2_scheme)):
    return usuario 

@app.post("/token")
async def obtener_token():
    return {"access_token": "faketoken", "token_type": "bearer"}

@app.get("/healthcheck")
async def healthcheck():
    return {"status": "API funcionando correctamente"}
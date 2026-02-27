from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from routers import devops_router

app = FastAPI()

app.include_router(devops_router, prefix="/ado", tags=["Azure DevOps"])


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"status": "ok"}

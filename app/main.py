from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import devices

app = FastAPI(title="Device Manager API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(devices.router, prefix="/api", tags=["devices"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
from __future__ import annotations

from fastapi import FastAPI

from rest.routers import setup_routers

app = FastAPI(title="trading-service API")
setup_routers(app)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("service:app", host="0.0.0.0", port=8000, reload=True)

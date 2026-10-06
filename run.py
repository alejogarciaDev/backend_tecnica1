import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)

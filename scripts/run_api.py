from agent.src.config import settings

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "agent.src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
    )

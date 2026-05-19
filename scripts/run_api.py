import os

from agent.src.config import settings

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", settings.API_PORT))
    uvicorn.run(
        "agent.src.api.main:app",
        host=settings.API_HOST,
        port=port,
        reload=False,
    )

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared limiter instance — mount on app via app.state.limiter
limiter = Limiter(key_func=get_remote_address)

# Reusable limit strings
LIMIT_GENERAL = "60/minute"   # standard routes
LIMIT_AI = "20/hour"          # AI / LLM-backed routes

# Usage in route handlers:
#
#   from app.core.limiter import limiter, LIMIT_GENERAL, LIMIT_AI
#
#   @router.get("/items")
#   @limiter.limit(LIMIT_GENERAL)
#   async def list_items(request: Request): ...
#
#   @router.post("/ai/chat")
#   @limiter.limit(LIMIT_AI)
#   async def ai_chat(request: Request): ...

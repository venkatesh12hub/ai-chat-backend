from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import json
import os
from typing import List, Dict

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store conversation history (use Redis/DB in production)
conversations: Dict[str, List[Dict]] = {}

GROQ_API_KEY = os.getenv("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")

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

SYSTEM_PROMPT = """You are a professional AI assistant.
- Solve math step-by-step.
- Write correct and efficient code.
- Explain clearly and concisely.
- Be accurate and direct.
- Never invent information about yourself.
"""

@app.get("/ping")
async def ping():
    return {"status": "server is running (Groq cloud mode)"}


@app.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        stream_chat(req),
        media_type="text/event-stream"
    )


async def stream_chat(req: ChatRequest):

    if req.session_id not in conversations:
        conversations[req.session_id] = []

    conversations[req.session_id].append({
        "role": "user",
        "content": req.message
    })

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversations[req.session_id])

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:

            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama3-70b-8192",
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7
                }
            ) as response:

                full_response = ""

                async for line in response.aiter_lines():

                    if line and line.startswith("data: "):
                        data_str = line.replace("data: ", "")

                        if data_str == "[DONE]":
                            conversations[req.session_id].append({
                                "role": "assistant",
                                "content": full_response
                            })

                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0]["delta"].get("content", "")

                            if delta:
                                full_response += delta
                                yield f"data: {json.dumps({'chunk': delta, 'done': False})}\n\n"

                        except:
                            continue

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"


@app.delete("/chat/clear")
async def clear_chat(session_id: str = "default"):
    conversations[session_id] = []
    return {"status": "cleared"}


@app.get("/chat/history")
async def get_history(session_id: str = "default"):
    return {"history": conversations.get(session_id, [])}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting CLOUD AI backend (Groq)")
    uvicorn.run(app, host="0.0.0.0", port=8000)


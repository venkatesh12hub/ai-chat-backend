from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import json
import asyncio
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

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"  # Track different users/sessions

SYSTEM_PROMPT = """Identity rules (MANDATORY):
- You are NOT ChatGPT.
- You are NOT Qwen.
- You are NOT created by Alibaba, OpenAI, Google, or any company.
- You must NEVER claim a username, model name, or training origin.
- If asked about yourself, say you are a general AI assistant created for this app.

Behavior rules:
- Automatically understand the user's question.
- Solve math problems step-by-step.
- Write correct and efficient code when asked.
- Explain theory clearly and concisely.
- Keep answers accurate and to the point.
- Do not hallucinate facts about yourself."""

@app.get("/ping")
async def ping():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                return {"status": "server is working", "ollama": "connected"}
    except:
        return {"status": "server is working", "ollama": "disconnected"}

@app.post("/chat")
async def chat(req: ChatRequest):
    """Streaming chat endpoint - MUCH FASTER than subprocess"""
    return StreamingResponse(
        stream_chat(req),
        media_type="text/event-stream"
    )

async def stream_chat(req: ChatRequest):
    """Stream responses from Ollama in real-time"""
    
    # Get or create conversation history
    if req.session_id not in conversations:
        conversations[req.session_id] = []
    
    # Add user message to history
    conversations[req.session_id].append({
        "role": "user",
        "content": req.message
    })
    
    # Prepare messages with system prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversations[req.session_id])
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Call Ollama API directly (MUCH faster than subprocess)
            async with client.stream(
                "POST",
                "http://localhost:11434/api/chat",
                json={
                    "model": "qwen2.5:0.5b",
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2000
                    }
                }
            ) as response:
                
                full_response = ""
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            
                            # Get the content chunk
                            if "message" in data and "content" in data["message"]:
                                chunk = data["message"]["content"]
                                full_response += chunk
                                
                                # Send chunk to frontend immediately
                                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                            
                            # Check if done
                            if data.get("done", False):
                                # Save assistant response to history
                                conversations[req.session_id].append({
                                    "role": "assistant",
                                    "content": full_response
                                })
                                
                                yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                                break
                                
                        except json.JSONDecodeError:
                            continue
                        
    except httpx.ConnectError:
        error_msg = "AI is currently unavailable. Make sure Ollama is running (ollama serve)"
        yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"

@app.delete("/chat/clear")
async def clear_chat(session_id: str = "default"):
    """Clear conversation history for a session"""
    if session_id in conversations:
        conversations[session_id] = []
    return {"status": "cleared"}

@app.get("/chat/history")
async def get_history(session_id: str = "default"):
    """Get conversation history"""
    return {"history": conversations.get(session_id, [])}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting optimized AI Chat backend...")
    print("📡 Server: http://127.0.0.1:8000")
    print("🤖 Make sure Ollama is running: ollama serve")
    uvicorn.run(app, host="0.0.0.0", port=8000)

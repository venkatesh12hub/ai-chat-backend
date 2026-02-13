from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import json
import base64
from typing import List, Dict, Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store conversation history
conversations: Dict[str, List[Dict]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    image_base64: Optional[str] = None  # For image input

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
- Do not hallucinate facts about yourself.
- When analyzing images, describe what you see in detail."""

@app.get("/ping")
async def ping():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                # Check for vision models
                has_vision = any("llava" in m["name"] or "vision" in m["name"] 
                               for m in models)
                return {
                    "status": "server is working",
                    "ollama": "connected",
                    "vision_available": has_vision
                }
    except:
        return {
            "status": "server is working",
            "ollama": "disconnected",
            "vision_available": False
        }

@app.get("/models")
async def get_models():
    """Get available models"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                return {
                    "models": [
                        {
                            "name": m["name"],
                            "has_vision": "llava" in m["name"] or "vision" in m["name"]
                        }
                        for m in models
                    ]
                }
    except:
        return {"models": []}

@app.post("/chat")
async def chat(req: ChatRequest):
    """Streaming chat endpoint with optional image support"""
    return StreamingResponse(
        stream_chat(req),
        media_type="text/event-stream"
    )

@app.post("/chat/image")
async def chat_with_image(
    message: str = Form(...),
    session_id: str = Form("default"),
    image: UploadFile = File(...)
):
    """Handle chat with image upload"""
    
    # Read and encode image
    image_data = await image.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    # Create request
    req = ChatRequest(
        message=message,
        session_id=session_id,
        image_base64=image_base64
    )
    
    return StreamingResponse(
        stream_chat(req),
        media_type="text/event-stream"
    )

async def stream_chat(req: ChatRequest):
    """Stream responses from Ollama with image support"""
    
    # Get or create conversation history
    if req.session_id not in conversations:
        conversations[req.session_id] = []
    
    # Determine model to use
    model = "llava" if req.image_base64 else "qwen2.5:0.5b"
    
    # Prepare message
    user_message = {
        "role": "user",
        "content": req.message
    }
    
    # Add image if present
    if req.image_base64:
        user_message["images"] = [req.image_base64]
    
    # Add to history
    conversations[req.session_id].append(user_message)
    
    # Prepare messages with system prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversations[req.session_id])
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            
            # Prepare payload
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 2000
                }
            }
            
            async with client.stream(
                "POST",
                "http://localhost:11434/api/chat",
                json=payload
            ) as response:
                
                full_response = ""
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            
                            if "message" in data and "content" in data["message"]:
                                chunk = data["message"]["content"]
                                full_response += chunk
                                
                                # Send chunk to frontend
                                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                            
                            if data.get("done", False):
                                # Save assistant response
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
        if req.image_base64:
            error_msg += "\nFor images, make sure you have llava installed: ollama pull llava"
        yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"

@app.delete("/chat/clear")
async def clear_chat(session_id: str = "default"):
    """Clear conversation history"""
    if session_id in conversations:
        conversations[session_id] = []
    return {"status": "cleared"}

@app.get("/chat/history")
async def get_history(session_id: str = "default"):
    """Get conversation history"""
    return {"history": conversations.get(session_id, [])}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AI Chat with Vision & Voice Support...")
    print("📡 Server: http://127.0.0.1:8000")
    print("🤖 Make sure Ollama is running: ollama serve")
    print("👁️ For image support: ollama pull llava")
    uvicorn.run(app, host="0.0.0.0", port=8000)
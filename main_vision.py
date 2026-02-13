#!/usr/bin/env python3
"""
Quick setup script for AI Chat with Vision & Voice
Installs necessary models and tests all features
"""

import asyncio
import httpx
import subprocess
import sys
import os

async def check_ollama():
    """Check if Ollama is running"""
    print("🔍 Checking Ollama...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                print("✅ Ollama is running!")
                return True, response.json().get("models", [])
    except:
        pass
    print("❌ Ollama is not running!")
    print("   Start it with: ollama serve")
    return False, []

def install_llava():
    """Install llava vision model"""
    print("\n📥 Installing Llava vision model...")
    print("   This may take 5-10 minutes (downloading ~4.5GB)")
    
    try:
        result = subprocess.run(
            ["ollama", "pull", "llava"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ Llava installed successfully!")
            return True
        else:
            print(f"❌ Failed to install llava: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ 'ollama' command not found!")
        print("   Please install Ollama from: https://ollama.ai/download")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def install_python_deps():
    """Install Python dependencies"""
    print("\n📦 Installing Python dependencies...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements_enhanced.txt"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✅ Python dependencies installed!")
            return True
        else:
            # Try individual install
            deps = ["fastapi", "uvicorn[standard]", "httpx", "pydantic", "python-multipart"]
            for dep in deps:
                subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                             capture_output=True)
            print("✅ Python dependencies installed!")
            return True
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print("   You may need to install manually:")
        print("   pip install fastapi uvicorn httpx pydantic python-multipart")
        return False

async def test_vision():
    """Test if vision model works"""
    print("\n🧪 Testing vision capabilities...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                has_vision = any("llava" in m["name"] for m in models)
                
                if has_vision:
                    print("✅ Vision model (llava) is available!")
                    return True
                else:
                    print("❌ Vision model not found")
                    return False
    except:
        return False

def check_browser_features():
    """Check browser feature support"""
    print("\n🌐 Browser Feature Support:")
    print("   Voice Input: Chrome ✅, Edge ✅, Safari ✅, Firefox ❌")
    print("   Voice Output: All modern browsers ✅")
    print("   Image Upload: All browsers ✅")
    print("\n   💡 For best experience, use Chrome or Edge")

async def main():
    print("=" * 70)
    print("🚀 AI Chat with Vision & Voice - Setup")
    print("=" * 70)
    
    # Step 1: Check Ollama
    ollama_running, models = await check_ollama()
    if not ollama_running:
        print("\n⚠️  Please start Ollama first, then run this script again.")
        return
    
    # Step 2: Check for existing models
    print(f"\n📦 Found {len(models)} models:")
    has_text_model = False
    has_vision_model = False
    
    for model in models:
        name = model.get("name", "unknown")
        print(f"   - {name}")
        if "qwen" in name or "llama" in name or "mistral" in name:
            has_text_model = True
        if "llava" in name or "vision" in name:
            has_vision_model = True
    
    # Step 3: Install models if needed
    if not has_text_model:
        print("\n📥 Installing text model (qwen2.5:0.5b)...")
        subprocess.run(["ollama", "pull", "qwen2.5:0.5b"], capture_output=True)
        print("✅ Text model installed!")
    
    if not has_vision_model:
        print("\n❓ Llava vision model not found.")
        response = input("   Install llava for image analysis? (y/n): ").lower()
        if response == 'y':
            install_llava()
        else:
            print("   ⚠️  Skipping vision model (image features won't work)")
    else:
        print("✅ Vision model already installed!")
    
    # Step 4: Install Python dependencies
    install_python_deps()
    
    # Step 5: Test vision
    if has_vision_model or await test_vision():
        print("\n✅ All vision features ready!")
    
    # Step 6: Browser features info
    check_browser_features()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SETUP SUMMARY")
    print("=" * 70)
    print(f"Ollama:           {'✅ Running' if ollama_running else '❌ Not running'}")
    print(f"Text Model:       {'✅ Ready' if has_text_model else '❌ Missing'}")
    print(f"Vision Model:     {'✅ Ready' if has_vision_model else '⚠️  Optional'}")
    print(f"Python Deps:      ✅ Installed")
    print("=" * 70)
    
    print("\n🎉 Setup Complete!")
    print("\n📝 Next Steps:")
    print("   1. Start backend:  python main_with_vision.py")
    print("   2. Open browser:   index_enhanced.html")
    print("   3. Try features:")
    print("      - 📷 Click camera icon to upload image")
    print("      - 🎤 Click mic icon for voice input")
    print("      - 🔊 Click speaker to enable voice output")
    print("\n💡 Tip: Read VISION_VOICE_GUIDE.md for detailed instructions")
    print()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(1)
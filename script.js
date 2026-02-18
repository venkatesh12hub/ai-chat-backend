// Configuration
const API_URL = "https://your-render-url.onrender.com";
const SESSION_ID = "user_" + Date.now();

let isGenerating = false;
let currentAIMessage = null;
let selectedImage = null;
let voiceEnabled = false;

// Voice Recognition
let recognition = null;
let isListening = false;

// Text-to-Speech
let speechSynthesis = window.speechSynthesis;

// Configure marked.js
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
  gfm: true
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  checkServerStatus();
  setupEventListeners();
  initVoiceRecognition();
});

function setupEventListeners() {
  const input = document.getElementById("user-input");

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
  });
}

function initVoiceRecognition() {
  // Check for browser support
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interimTranscript += transcript;
        }
      }

      // Update input field
      const input = document.getElementById('user-input');
      if (finalTranscript) {
        input.value = input.value + finalTranscript;
      }
      
      // Show interim results
      const transcriptEl = document.getElementById('voice-transcript');
      if (transcriptEl) {
        transcriptEl.textContent = interimTranscript;
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      stopVoiceInput();
    };

    recognition.onend = () => {
      if (isListening) {
        recognition.start(); // Restart if still listening
      }
    };
  } else {
    console.warn('Speech recognition not supported in this browser');
  }
}

function toggleVoiceInput() {
  if (!recognition) {
    alert('Voice input is not supported in your browser. Please use Chrome, Edge, or Safari.');
    return;
  }

  if (isListening) {
    stopVoiceInput();
  } else {
    startVoiceInput();
  }
}

function startVoiceInput() {
  const voiceBtn = document.getElementById('voice-btn');
  const indicator = document.getElementById('voice-indicator');
  
  isListening = true;
  voiceBtn.classList.add('active');
  indicator.style.display = 'block';
  
  try {
    recognition.start();
  } catch (e) {
    console.error('Failed to start recognition:', e);
  }
}

function stopVoiceInput() {
  const voiceBtn = document.getElementById('voice-btn');
  const indicator = document.getElementById('voice-indicator');
  
  isListening = false;
  voiceBtn.classList.remove('active');
  indicator.style.display = 'none';
  
  if (recognition) {
    recognition.stop();
  }
}

function toggleVoiceOutput() {
  voiceEnabled = !voiceEnabled;
  const icon = document.getElementById('voice-icon');
  const btn = document.getElementById('voice-toggle');
  
  if (voiceEnabled) {
    icon.textContent = '🔊';
    btn.classList.add('active');
    btn.title = 'Voice output enabled';
  } else {
    icon.textContent = '🔇';
    btn.classList.remove('active');
    btn.title = 'Voice output disabled';
    // Stop any ongoing speech
    speechSynthesis.cancel();
  }
}

function speakText(text) {
  if (!voiceEnabled) return;
  
  // Cancel any ongoing speech
  speechSynthesis.cancel();
  
  // Clean text for speech (remove markdown, code blocks, etc.)
  const cleanText = text
    .replace(/```[\s\S]*?```/g, 'code block')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[*_#\[\]()]/g, '')
    .replace(/\n/g, ' ')
    .trim();
  
  if (!cleanText) return;
  
  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  utterance.volume = 1.0;
  
  // Try to use a good voice
  const voices = speechSynthesis.getVoices();
  const preferredVoice = voices.find(v => v.lang.startsWith('en') && v.name.includes('Google')) ||
                         voices.find(v => v.lang.startsWith('en'));
  if (preferredVoice) {
    utterance.voice = preferredVoice;
  }
  
  speechSynthesis.speak(utterance);
}

function handleImageSelect(event) {
  const file = event.target.files[0];
  if (!file) return;

  // Check file type
  if (!file.type.startsWith('image/')) {
    alert('Please select an image file');
    return;
  }

  // Check file size (max 10MB)
  if (file.size > 10 * 1024 * 1024) {
    alert('Image is too large. Maximum size is 10MB');
    return;
  }

  selectedImage = file;

  // Show preview
  const reader = new FileReader();
  reader.onload = (e) => {
    const previewImg = document.getElementById('preview-img');
    const previewDiv = document.getElementById('image-preview');
    
    previewImg.src = e.target.result;
    previewDiv.style.display = 'block';
  };
  reader.readAsDataURL(file);
}

function removeImage() {
  selectedImage = null;
  document.getElementById('image-preview').style.display = 'none';
  document.getElementById('image-input').value = '';
}

async function checkServerStatus() {
  const statusDot = document.getElementById("status");
  try {
    const response = await fetch(`${API_URL}/chat`);
    const data = await response.json();
    
    if (data.status === "server is working") {
      statusDot.style.background = "#4ade80";
      statusDot.title = "Server connected" + (data.vision_available ? " (Vision enabled)" : "");
    } else {
      statusDot.style.background = "#fbbf24";
      statusDot.title = "Ollama disconnected";
    }
  } catch {
    statusDot.style.background = "#ef4444";
    statusDot.title = "Server disconnected";
  }
}

async function sendMessage() {
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const sendBtn = document.getElementById("send-btn");

  const text = input.value.trim();
  if (!text || isGenerating) return;

  // Stop voice input if active
  if (isListening) {
    stopVoiceInput();
  }

  // Add user message
  addUserMessage(text, selectedImage);
  
  input.value = "";
  input.style.height = 'auto';

  isGenerating = true;
  sendBtn.disabled = true;

  // Create AI message container
  currentAIMessage = createAIMessageElement();
  chatBox.appendChild(currentAIMessage);
  scrollToBottom();

  try {
    let response;

    if (selectedImage) {
      // Send with image
      const formData = new FormData();
      formData.append('message', text);
      formData.append('session_id', SESSION_ID);
      formData.append('image', selectedImage);

      response = await fetch(`${API_URL}/chat/image`, {
        method: "POST",
        body: formData
      });

      removeImage();
    } else {
      // Send text only
      response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          message: text,
          session_id: SESSION_ID
        })
      });
    }

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    // Read streaming response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let aiResponse = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.error) {
              updateAIMessage(currentAIMessage, `<span class="error">❌ ${data.error}</span>`);
              break;
            }

            if (data.chunk) {
              aiResponse += data.chunk;
              updateAIMessage(currentAIMessage, aiResponse);
            }

            if (data.done) {
              updateAIMessage(currentAIMessage, aiResponse, true);
              // Speak the response if voice is enabled
              speakText(aiResponse);
              break;
            }
          } catch (e) {
            console.error('Parse error:', e);
          }
        }
      }
    }

  } catch (error) {
    console.error('Error:', error);
    updateAIMessage(
      currentAIMessage, 
      `<span class="error">❌ Backend error. Make sure the server is running.</span>`
    );
  } finally {
    isGenerating = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

function addUserMessage(content, image) {
  const chatBox = document.getElementById("chat-box");
  const messageDiv = document.createElement("div");
  messageDiv.className = "user";

  let html = `<b>You:</b> ${escapeHtml(content)}`;
  
  if (image) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = document.createElement('img');
      img.src = e.target.result;
      img.style.maxWidth = '200px';
      img.style.borderRadius = '8px';
      img.style.marginTop = '8px';
      messageDiv.appendChild(img);
    };
    reader.readAsDataURL(image);
  }

  messageDiv.innerHTML = html;
  chatBox.appendChild(messageDiv);
  scrollToBottom();
}

function createAIMessageElement() {
  const messageDiv = document.createElement("div");
  messageDiv.className = "ai";
  messageDiv.innerHTML = `
    <b>AI:</b>
    <div class="typing-indicator">
      <span></span><span></span><span></span>
    </div>
  `;
  return messageDiv;
}

function updateAIMessage(element, content, isComplete = false) {
  if (!element) return;

  if (isComplete) {
    element.innerHTML = `<b>AI:</b><div>${marked.parse(content)}</div>`;
    element.querySelectorAll('pre code').forEach((block) => {
      hljs.highlightElement(block);
    });
  } else {
    const formattedContent = content.replace(/\n/g, '<br>');
    element.innerHTML = `<b>AI:</b> ${formattedContent}<span class="cursor">|</span>`;
  }

  scrollToBottom();
}

function clearChat() {
  const chatBox = document.getElementById("chat-box");
  
  if (confirm("Clear all chat history?")) {
    chatBox.innerHTML = "";
    
    fetch(`${API_URL}/chat/clear?session_id=${SESSION_ID}`, {
      method: 'DELETE'
    }).catch(console.error);
    
    removeImage();
  }
}

function scrollToBottom() {
  const chatBox = document.getElementById("chat-box");
  chatBox.scrollTop = chatBox.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Periodic server check
setInterval(checkServerStatus, 30000);

// Load voices for speech synthesis
speechSynthesis.onvoiceschanged = () => {
  speechSynthesis.getVoices();
};

// Add cursor animation
const style = document.createElement('style');
style.textContent = `
  .cursor {
    animation: blink 1s infinite;
  }
  @keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
  }
`;
document.head.appendChild(style);

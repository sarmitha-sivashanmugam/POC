import os
import json
import aiohttp
import asyncio
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types
from . import constants
from dotenv import load_dotenv


load_dotenv()


client = genai.Client(
    api_key=os.getenv("API_KEY"),
    http_options={"api_version": "v1alpha"}
)


class VoiceChatConsumer(AsyncWebsocketConsumer):
    """
    This consumer handles a WebSocket connection to a client and manages a
    real-time, bidirectional audio stream with the Gemini Live API.
    """

    async def connect(self):
        # Check authentication before accepting connection
        self.user = self.scope["user"]
        
        if not self.user or self.user.is_anonymous:
            print("Unauthenticated user trying to connect to voice chat")
            await self.close(code=4001)  # Close with authentication failure code
            return
        
        print(f"WebSocket connection accepted for user: {self.user.username}")
        
        self.session = None
        self.session_context = None
        self.conversation_data = {
            'id': f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'messages': []
        }
        await self.accept() # Accept the WebSocket Handshake

    async def disconnect(self, close_code):
        # Only process conversation if AI completed the consultation
        if self.conversation_data and self.conversation_data['messages']:
            # Check if AI said the completion message
            ai_completed = False
            for message in self.conversation_data['messages']:
                if message.get('role') == 'ai':
                    text = message.get('text', '').lower()
                    if ('thank you for providing this information' in text or 
                        'i have collected all the necessary details' in text):
                        ai_completed = True
                        break
            
            if ai_completed:
                try:
                    # Send to process-conversation API only if AI completed
                    await self.send_conversation_to_api(self.conversation_data)
                    print(f"Conversation data sent for processing: {self.conversation_data['id']}")
                except Exception as e:
                    print(f"Error sending conversation: {e}")
            else:
                print(f"Conversation not completed by AI - skipping processing: {self.conversation_data['id']}")
        
        # Clean up the Gemini session when the client disconnects.
        if self.session and self.session_context:
            try:
                await self.session_context.__aexit__(None, None, None)
            except:
                pass
            self.session = None
            self.session_context = None

    async def receive(self, text_data=None, bytes_data=None):
        # This consumer now primarily handles raw audio bytes.
        if bytes_data:
            if not self.session:
                # On the first audio chunk, establish the connection to Gemini Live API.
                await self.start_gemini_session()

            # Forward the audio chunk to Gemini.
            if self.session:
                await self.session.send_realtime_input(
                    audio=types.Blob(data=bytes_data, mime_type="audio/pcm;rate=16000")
                )

    async def start_gemini_session(self):
        """Initializes a new live session with the Gemini API."""
        # User is already authenticated from connect() method
        print(f"Starting Gemini session for user: {self.user.username} ({self.user.email})")
        
        # Initialize conversation processor with authenticated user
        # Conversation data is already initialized in connect()
        
        config = {
            
            "generation_config": {"response_modalities": ["AUDIO"]},
            "enable_affective_dialog": True,
            "speech_config": {
                "voice_config": {"prebuilt_voice_config": {"voice_name": "Zephyr"}},
            },
             
            "input_audio_transcription": {},  # Enable input transcription
            "output_audio_transcription": {},  # Enable output transcription
            "system_instruction": constants.AI_SYSTEM_INSTRUCTION,
        }
        self.session_context = client.aio.live.connect(model=constants.GEMINI_MODEL_NAME, config=config)
        self.session = await self.session_context.__aenter__()
        
        # Send initial text message to start the conversation
        await self.send_initial_greeting()
        
        # Start a background task to listen for responses from Gemini.
        asyncio.create_task(self.listen_for_gemini_responses())

    async def send_initial_greeting(self):
        """Send initial text message to start the conversation"""
        if not self.session:
            return
        
        try:
            # Send initial text message to trigger AI response
            await self.session.send_realtime_input(
                text="Hello"
            )
            print("Initial greeting sent to Gemini")
        except Exception as e:
            print(f"Error sending initial greeting: {e}")

    async def listen_for_gemini_responses(self):
        """Receives audio chunks from Gemini and streams them to the client."""
        if not self.session:
            return
        try:
            while True:
                # Continuously listen for new turns/responses
                turn = self.session.receive()
                async for response in turn:
                    # Handle transcriptions from server_content
                    if hasattr(response, 'server_content') and response.server_content:
                        server_content = response.server_content
                        
                        # Handle input transcription (user speech)
                        if hasattr(server_content, 'input_transcription') and server_content.input_transcription:
                            if hasattr(server_content.input_transcription, 'text') and server_content.input_transcription.text:
                                user_text = server_content.input_transcription.text
                                
                                # Store in conversation processor
                                # Add user message to conversation data
                                self.conversation_data['messages'].append({
                                    'role': 'user',
                                    'text': user_text
                                })
                                
                                await self.send(text_data=json.dumps({
                                    'type': 'user_transcript',
                                    'text': user_text
                                }))
                        
                        # Handle output transcription (Rishi's speech)
                        if hasattr(server_content, 'output_transcription') and server_content.output_transcription:
                            if hasattr(server_content.output_transcription, 'text') and server_content.output_transcription.text:
                                ai_text = server_content.output_transcription.text
                                
                                # Store in conversation processor
                                # Add AI message to conversation data
                                self.conversation_data['messages'].append({
                                    'role': 'ai',
                                    'text': ai_text
                                })
                                
                                await self.send(text_data=json.dumps({
                                    'type': 'ai_transcript',
                                    'text': ai_text
                                }))
                    
                    # Handle audio data from Gemini
                    if response.data:
                        # Forward the received audio chunk directly to the client.
                        await self.send(bytes_data=response.data)
        except Exception as e:
            # Connection closed or error - silently handle it
            print(f"Gemini session error: {e}")
            pass
    
    async def send_conversation_to_api(self, conversation_data):
        """Send conversation data to the product recommendation API"""
        try:
            
            
            print("===== SENDING CONVERSATION TO API =====")
            print(f"Conversation ID: {conversation_data['id']}")
            print(f"Messages count: {len(conversation_data['messages'])}")
            
            # Send to conversation processing API
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:8000/api/process-conversation/"
                payload = {
                    'conversation': conversation_data
                }
                
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        print("API processing successful:")
                        print(f"Status: {result.get('success')}")
                        if result.get('success') and 'result' in result:
                            api_result = result['result']
                            print(f"Patient info: {api_result.get('patient_info', {})}")
                            print(f"Initial filtered products: {api_result.get('initial_filtered_count', 0)}")
                            print(f"Final filtered products: {api_result.get('final_filtered_count', 0)}")
                            print(f"Filtering applied: {api_result.get('filtering_applied', 'Unknown')}")
                            
                            # Send result to frontend to trigger cart addition
                            await self.send(text_data=json.dumps({
                                'type': 'llm_result',
                                'result': api_result
                            }))
                            print("✅ LLM result sent to frontend for cart processing")
                            
                    else:
                        print(f"❌ API error: {response.status}")
                        
        except Exception as e:
            print(f"❌ Error sending to API: {e}")

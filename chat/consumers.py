import os
import json
import asyncio
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types
from . import constants
from .tools_simplified import TOOL_DEFINITIONS, execute_tool
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
        
        # Start Gemini session and send initial greeting immediately
        await self.start_gemini_session()

    async def disconnect(self, close_code):
        # Only process conversation if AI completed the consultation
        if self.conversation_data and self.conversation_data['messages']:
            # Check if AI said the completion message
            # Tool calling handles real-time recommendations - no post-processing needed
            print(f"Tool calling handles real-time recommendations during conversation: {self.conversation_data['id']}")
        
        # Clean up the Gemini session when the client disconnects.
        if self.session and self.session_context:
            try:
                await self.session_context.__aexit__(None, None, None)
            except:
                pass
            self.session = None
            self.session_context = None
        
        print(f"WebSocket disconnected for user: {self.user.username} (code: {close_code})")

    async def receive(self, text_data=None, bytes_data=None):
        # Handle text messages from Web Speech API
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get('type') == 'text_input':
                    text = data.get('text', '').strip()
                    if text and self.session:
                        print(f"Received text input from user: {text}")
                        await self.session.send_realtime_input(text=text)
                    return
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON received: {text_data}")
                pass
        
        # Handle binary audio data (for audio responses only)
        if bytes_data:
            print(f"❌ Unexpected audio data received - should only receive text now")
            # No longer processing audio input

    async def start_gemini_session(self):
        """Initializes a new live session with the Gemini API."""
        # User is already authenticated from connect() method
        print(f"Starting Gemini session for user: {self.user.username} ({self.user.email})")
        
        # Check API key first
        api_key = os.getenv("API_KEY")
        if not api_key:
            print("❌ ERROR: API_KEY environment variable is not set!")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'API key not configured. Please contact administrator.'
            }))
            await self.close(code=4002)
            return
        
        try:
            # Initialize conversation processor with authenticated user
            # Conversation data is already initialized in connect()
            
            config = {
                "tools": TOOL_DEFINITIONS,  # Add tool schemas for function calling
                "generation_config": {"response_modalities": ["AUDIO"]},
                "enable_affective_dialog": True,
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": "Zephyr"}},
                },
                
                # No input audio transcription - using Web Speech API instead
                "output_audio_transcription": {},  # Enable output transcription
                "system_instruction": constants.AI_SYSTEM_INSTRUCTION,
            }
            
            print(f"TOOLS CONFIGURED: {len(TOOL_DEFINITIONS)} tools")
            for i, tool in enumerate(TOOL_DEFINITIONS, 1):
                if hasattr(tool, 'function_declarations'):
                    for func in tool.function_declarations:
                        print(f"   {i}. {func.name}: {func.description}")
                        print(f"      Required params: {func.parameters.required if hasattr(func.parameters, 'required') else 'None'}")
                        print(f"      Properties: {list(func.parameters.properties.keys()) if hasattr(func.parameters, 'properties') else 'None'}")
            
            print(f"Connecting to Gemini Live API with model: {constants.GEMINI_MODEL_NAME}")
            self.session_context = client.aio.live.connect(model=constants.GEMINI_MODEL_NAME, config=config)
            self.session = await self.session_context.__aenter__()
            print("✅ Gemini session established successfully")
            
            # Send initial text message to start the conversation
            await self.send_initial_greeting()
            
            # Start a background task to listen for responses from Gemini.
            asyncio.create_task(self.listen_for_gemini_responses())
            
        except Exception as e:
            print(f"❌ ERROR starting Gemini session: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Send error message to client
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to connect to AI service: {str(e)}'
            }))
            
            # Close the WebSocket connection
            await self.close(code=4003)

    async def send_initial_greeting(self):
        """Send initial text message to start the conversation"""
        if not self.session:
            return
        
        try:
            # Wait a moment for session to be fully ready
            await asyncio.sleep(0.5)
            
            # Send initial text message to trigger AI response
            print("Sending initial greeting to Gemini...")
            await self.session.send_realtime_input(
                text="Hello"
            )
            print("✅ Initial greeting sent to Gemini: 'Hello'")
            
            # Wait a bit more to ensure the message is processed
            await asyncio.sleep(1.0)
            print("Waiting for AI response...")
            
            # Send signal to frontend to start Web Speech API
            await self.send(text_data=json.dumps({
                'type': 'start_speech_recognition'
            }))
            print(" Signal sent to start Web Speech API")
        except Exception as e:
            print(f"❌ Error sending initial greeting: {e}")

    async def listen_for_gemini_responses(self):
        """Receives audio chunks from Gemini and streams them to the client."""
        if not self.session:
            print("❌ No Gemini session available for listening")
            return
        
        retry_count = 0
        max_retries = 2
        
        while retry_count < max_retries:
            try:
                print(f" Starting to listen for Gemini responses (attempt {retry_count + 1}/{max_retries})")
                
                while True:
                    # Continuously listen for new turns/responses
                    turn = self.session.receive()
                    async for response in turn:
                        print(f"Processing response: {type(response).__name__}")
                        
                        # Handle tool calls from Gemini - CORRECTED FORMAT
                        if response.tool_call:
                            print(f"TOOL CALLS DETECTED: {len(response.tool_call.function_calls)}")
                            await self.handle_tool_calls(response.tool_call)
                        else:
                            print(f" No tool calls in this response")
                            # Debug: Check what response contains
                            print(f"Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                            if hasattr(response, 'server_content'):
                                print(f"Has server_content: {response.server_content is not None}")
                        
                        # Handle server content for transcriptions
                        if hasattr(response, 'server_content') and response.server_content:
                            server_content = response.server_content
                            
                            # Handle output transcription (AI's speech) - input transcription handled by Web Speech API
                            if hasattr(server_content, 'output_transcription') and server_content.output_transcription:
                                if hasattr(server_content.output_transcription, 'text') and server_content.output_transcription.text:
                                    # DEBUG: Log raw text from Gemini
                                    raw_ai_text = server_content.output_transcription.text
                                    print(f"RAW GEMINI TEXT: '{raw_ai_text}'")
                                    print(f"RAW TEXT LENGTH: {len(raw_ai_text)}")
                                    print(f"RAW TEXT TYPE: {type(raw_ai_text)}")
                                    
                                    ai_text = raw_ai_text.strip()
                                    
                                    if ai_text:  # Only process non-empty text
                                        print(f" RAW AI TRANSCRIPT: '{ai_text}'")
                                        
                                        # Store in conversation processor
                                        # Add AI message to conversation data
                                        self.conversation_data['messages'].append({
                                            'role': 'ai',
                                            'text': ai_text
                                        })
                                        
                                        # Send AI transcript to frontend (no preprocessing)
                                        await self.send(text_data=json.dumps({
                                            'type': 'ai_transcript',
                                            'text': ai_text
                                        }))
                                        print(f"✅ AI transcript sent to frontend: '{ai_text}'")
                            
                            # Handle audio data from Gemini
                            if hasattr(response, 'data') and response.data:
                                # Forward the received audio chunk directly to the client.
                                await self.send(bytes_data=response.data)
                                print(f"Audio chunk sent to frontend: {len(response.data)} bytes")
                
            except Exception as e:
                retry_count += 1
                error_type = type(e).__name__
                error_message = str(e)
                
                print(f"❌ Gemini session error (attempt {retry_count}/{max_retries}): {error_type}: {error_message}")
                
                # Check if it's a connection error
                if "ConnectionClosedError" in error_type or "1011" in error_message or "internal error" in error_message.lower():
                    print(f"Connection error detected, attempting to reconnect...")
                    
                    if retry_count < max_retries:
                        try:
                            # Clean up existing session
                            if self.session_context:
                                try:
                                    await self.session_context.__aexit__(None, None, None)
                                except:
                                    pass
                                self.session_context = None
                                self.session = None
                            
                            # Wait before retrying
                            await asyncio.sleep(2)
                            
                            # Try to reconnect
                            print(f" Attempting to reconnect to Gemini API...")
                            await self.start_gemini_session()
                            return  # Exit the retry loop if reconnection succeeds
                            
                        except Exception as reconnect_error:
                            print(f"❌ Reconnection failed: {reconnect_error}")
                            continue
                    else:
                        print(f"❌ Max retries reached. Connection failed permanently.")
                        break
                else:
                    print(f"❌ Non-connection error, not retrying: {error_message}")
                    break
        
        # If we get here, all retries failed
        print(f"❌ All retry attempts failed. Sending error to client.")
        try:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Connection to AI service lost. Please refresh the page and try again.'
            }))
        except:
            pass  # Client might have already disconnected
    
    async def handle_tool_calls(self, tool_calls):
        """Handle tool calls from Gemini and execute them using proper Google Gemini API format."""
        try:
            from google.genai import types
            
            print("=" * 80)
            print("TOOL CALL DETECTED - STARTING DEBUG SESSION")
            print("=" * 80)
            print(f"Total function calls: {len(tool_calls.function_calls)}")
            print(f"User: {self.user.username if self.user else 'Anonymous'}")
            print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 80)
            
            for i, function_call_obj in enumerate(tool_calls.function_calls, 1):
                print(f"\nTOOL CALL #{i}")
                print(f"   Tool Name: {function_call_obj.name}")
                print(f"   Function ID: {function_call_obj.id}")
                print(f"   Parameters: {json.dumps(function_call_obj.args, indent=2)}")
                print(f"   Parameter Count: {len(function_call_obj.args) if function_call_obj.args else 0}")
                
                # Execute the tool with detailed logging
                print(f"\nEXECUTING TOOL: {function_call_obj.name}")
                print("-" * 40)
                
                start_time = datetime.now()
                result = await execute_tool(function_call_obj.name, function_call_obj.args, self.user)
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                print(f"Execution Time: {execution_time:.3f} seconds")
                print(f"Tool Execution Complete")
                print(f"Result Success: {result.get('success', False)}")
                print(f"Result Keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                
                if result.get('success'):
                    if 'products' in result:
                        print(f"Products Found: {result.get('count', 0)}")
                        for j, product in enumerate(result.get('products', [])[:3], 1):
                            print(f"   {j}. {product.get('name', 'Unknown')} - ${product.get('price', 0)}")
                        if len(result.get('products', [])) > 3:
                            print(f"   ... and {len(result.get('products', [])) - 3} more products")
                    
                    if 'added_items' in result:
                        print(f"Items Added to Cart: {len(result.get('added_items', []))}")
                        for item in result.get('added_items', []):
                            print(f"   - {item.get('product_name', 'Unknown')} (x{item.get('quantity', 1)})")
                    
                    if 'cart' in result:
                        cart = result.get('cart', {})
                        print(f"Cart Summary:")
                        print(f"   Total Items: {cart.get('total_items', 0)}")
                        print(f"   Total Price: ${cart.get('total_price', 0)}")
                else:
                    print(f"Tool Execution Failed: {result.get('error', 'Unknown error')}")
                
                print(f"\nSENDING RESPONSE TO GEMINI")
                print("-" * 40)
                
                # Create proper function response using Google Gemini API format
                function_response = types.FunctionResponse(
                    name=function_call_obj.name,
                    response={"result": result},
                    id=function_call_obj.id,
                )
                
                print(f"Function Response Created:")
                print(f"   Name: {function_response.name}")
                print(f"   ID: {function_response.id}")
                print(f"   Response Size: {len(str(result))} characters")
                
                # Send tool result back to Gemini using proper API
                await self.session.send_tool_response(
                    function_responses=function_response
                )
                print(f"Response sent to Gemini successfully")
                
                # Send tool result to frontend for real-time updates
                await self.send(text_data=json.dumps({
                    'type': 'tool_result',
                    'tool_name': function_call_obj.name,
                    'result': result
                }))
                print(f"Frontend notification sent")
                
                print(f"\nTOOL CALL #{i} COMPLETED SUCCESSFULLY")
                print("=" * 80)
                
        except Exception as e:
            print(f"\n❌ TOOL CALL ERROR")
            print("=" * 80)
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            print(f"Error Details: {repr(e)}")
            import traceback
            print(f"Traceback:")
            traceback.print_exc()
            print("=" * 80)
            
            # Send error back to Gemini
            await self.session.send_realtime_input(
                text=f"Tool execution error: {str(e)}"
            )
    

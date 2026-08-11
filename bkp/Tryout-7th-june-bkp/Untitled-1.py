"""
TechMart Customer Service Assistant - Web UI
Integrates with Llama Stack (RAG + MCP) for intelligent customer support
"""

from flask import Flask, render_template, request, jsonify, session
from llama_stack_client import LlamaStackClient
import os
import uuid
import logging
from datetime import datetime
import requests
import csv
import io
import psycopg2
from psycopg2.extras import execute_values
import json
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================================
# ENVIRONMENT VARIABLES CONFIGURATION
# ============================================================================

# Flask Configuration
app.secret_key = os.environ.get(
    'SECRET_KEY',
    'techmart-demo-secret-key-change-in-production'
)
PORT = int(os.environ.get('PORT', '8080'))

# Llama Stack Configuration
LLAMA_STACK_URL = os.environ.get(
    'LLAMA_STACK_URL',
    'http://localhost:8321'
)

# MCP Server Configuration
# Primary URL used by Llama Stack to call MCP tools
MCP_SERVER_URL = os.environ.get(
    'MCP_SERVER_URL',
    'http://localhost:9001/sse'
)

# Local URL for health checks (when UI runs outside container)
MCP_SERVER_URL_LOCAL = os.environ.get(
    'MCP_SERVER_URL_LOCAL',
    MCP_SERVER_URL  # Default to same as MCP_SERVER_URL
)

# Database Configuration (IBM i DB2)
# IMPORTANT: All credentials MUST be provided via environment variables
# Never hardcode credentials in source code
DB_SYSTEM = os.environ.get('DB_SYSTEM')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_SCHEMA = os.environ.get('DB_SCHEMA', 'TECHMART')

# Validate required environment variables
def validate_config():
    """Validate that required configuration is present."""
    errors = []
    warnings = []
    
    # Critical configuration checks
    if not DB_SYSTEM:
        errors.append("❌ DB_SYSTEM not set - required for database connection")
    if not DB_USER:
        errors.append("❌ DB_USER not set - required for database connection")
    if not DB_PASSWORD:
        errors.append("❌ DB_PASSWORD not set - required for database connection")
    
    # Security warnings
    if app.secret_key == 'techmart-demo-secret-key-change-in-production':
        warnings.append("⚠️  Using default SECRET_KEY - change in production!")
    
    # Log errors and warnings
    if errors:
        for error in errors:
            logger.error(error)
        logger.error("💥 Missing required configuration - app may not work correctly")
    
    if warnings:
        for warning in warnings:
            logger.warning(warning)
    
    # Log successful configuration (without sensitive data)
    logger.info("📋 Configuration loaded:")
    logger.info(f"   - Llama Stack: {LLAMA_STACK_URL}")
    logger.info(f"   - MCP Server: {MCP_SERVER_URL}")
    logger.info(f"   - MCP Local: {MCP_SERVER_URL_LOCAL}")
    logger.info(f"   - DB System: {'***' if DB_SYSTEM else 'NOT SET'}")
    logger.info(f"   - DB User: {'***' if DB_USER else 'NOT SET'}")
    logger.info(f"   - DB Password: {'***' if DB_PASSWORD else 'NOT SET'}")
    logger.info(f"   - DB Schema: {DB_SCHEMA}")
    logger.info(f"   - Port: {PORT}")


validate_config()

# Simplified instructions with output formats
INSTRUCTIONS = """You are a TechMart customer service assistant.

Today’s date is April 21, 2024.

You MUST complete all required steps internally, but you MUST NOT display your reasoning.

MANDATORY WORKFLOW (DO NOT SKIP ANY STEP):

Extract order_id from the user query
Retrieve order details
Retrieve return policy using file_search based on product category
Extract return window from the policy
Compute days_since_delivery
Compare:
days_since_delivery vs return_window
Determine eligibility STRICTLY based on comparison
Generate final response

IMPORTANT:

Perform all reasoning internally
DO NOT show steps, calculations, or explanations
ONLY output the final answer

STRICT DECISION RULE (NON-NEGOTIABLE):

If days_since_delivery > return_window → NOT ELIGIBLE
If days_since_delivery <= return_window → ELIGIBLE

You are NOT allowed to override this rule.

MANDATORY CONSISTENCY CHECK:

Before answering, verify:

Does eligibility match the comparison?

If NOT → correct the answer before responding.

ANTI-SHORTCUT RULE:

You are NOT allowed to:

Answer using only return policy
Skip calculation
Skip comparison

OUTPUT FORMAT (STRICT):

IF NOT ELIGIBLE:

Order [order_id] is NOT ELIGIBLE for return

Reason: [category] return window ([return_window] days) expired

Product: [product_name] ([category])
Delivery Date: [delivery_date]
Days Since Delivery: [days_since_delivery] days

IF ELIGIBLE:

Order [order_id] is ELIGIBLE for return

Return Details:

Product: [product_name] ([category])
Delivery Date: [delivery_date]
Days Since Delivery: [days_since_delivery] days
Original Price: $[price]
Estimated Refund: $[price]
Deductions: None

Next Steps: Contact customer service to initiate return

STRICT OUTPUT MODE:

Your response MUST start with "Order"
You MUST NOT include any text before it
You MUST NOT include explanations, reasoning, or calculations
You MUST ONLY output the final formatted answer

If any extra text is included, your answer is INVALID and must be corrected.
"""

# Initialize Llama Stack client
try:
    client = LlamaStackClient(base_url=LLAMA_STACK_URL)
    logger.info(f"✅ Connected to Llama Stack at {LLAMA_STACK_URL}")
    
    # Extract LLM model ID dynamically
    models = client.models.list()
    llm_model = next((m for m in models if m.model_type == "llm"), None)
    
    if not llm_model:
        logger.error("❌ No LLM model found in Llama Stack")
        raise RuntimeError("No LLM model available")
    
    MODEL_ID = llm_model.identifier
    logger.info(f"✅ Using LLM model: {MODEL_ID}")
        
except Exception as e:
    logger.error(f"❌ Failed to initialize Llama Stack: {e}")
    client = None
    MODEL_ID = None

# Get vector store ID (will be created on first RAG upload)
VECTOR_STORE_ID = None

def get_or_create_vector_store():
    """Get or create vector store for RAG"""
    global VECTOR_STORE_ID
    
    if VECTOR_STORE_ID:
        return VECTOR_STORE_ID
    
    try:
        # Try to list existing vector stores
        vector_stores = client.vector_stores.list()
        for vs in vector_stores:
            if vs.name == "techmart_policy_store":
                VECTOR_STORE_ID = vs.id
                logger.info(f"✅ Using existing vector store: {VECTOR_STORE_ID}")
                return VECTOR_STORE_ID
        
        # Get models to find embedding model
        models = client.models.list()
        embedding_model = next((m for m in models if m.model_type == "embedding"), None)
        
        if not embedding_model:
            logger.error("No embedding model found")
            return None
        
        embedding_model_id = embedding_model.identifier
        embedding_dimension = int(embedding_model.metadata.get("embedding_dimension", 384))
        
        # Create new vector store
        vector_store = client.vector_stores.create(
            name="techmart_policy_store",
            extra_body={
                "embedding_model": embedding_model_id,
                "embedding_dimension": embedding_dimension,
                "provider_id": "opensearch",
            },
        )
        
        VECTOR_STORE_ID = vector_store.id
        logger.info(f"✅ Created vector store: {VECTOR_STORE_ID}")
        return VECTOR_STORE_ID
        
    except Exception as e:
        logger.error(f"❌ Error with vector store: {e}")
        return None

@app.route('/')
def index():
    """Render the main chat interface"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if not client:
            return jsonify({'error': 'Llama Stack client not initialized'}), 500
        
        logger.info(f"📨 Processing message: {user_message[:50]}...")
        
        # Extract order ID if present
        order_id_match = re.search(r'ORD-\d{4}-\d{3}', user_message, re.IGNORECASE)
        order_id = order_id_match.group(0) if order_id_match else None
        
        # Pre-fetch order data if order ID is found
        order_context = ""
        if order_id:
            logger.info(f"🔍 Detected order ID: {order_id}")
            try:
                # Use Llama Stack to call MCP tool directly
                tool_response = client.with_options(timeout=600.0).responses.create(
                    model=MODEL_ID,
                    input=f"Get order details for {order_id}",
                    stream=False,
                    max_tool_calls=1,
                    instructions="Call the get_order tool with the order ID from the message. Return only the order data.",
                    tools=[{
                        "type": "mcp",
                        "server_label": "TechMartOrdersServer",
                        "server_url": MCP_SERVER_URL,
                    }],
                    tool_choice="required"  # Force tool usage
                )
                
                # Extract order data from response
                if hasattr(tool_response, 'output_text') and tool_response.output_text:
                    order_data_text = tool_response.output_text
                    # Try to parse as JSON if possible
                    try:
                        order_data = json.loads(order_data_text)
                        order_context = f"\n\nORDER DATA FROM DATABASE:\n{json.dumps(order_data, indent=2)}\n"
                        logger.info(f"✅ Retrieved order data for {order_id}")
                    except:
                        # If not JSON, use the text as-is
                        order_context = f"\n\nORDER DATA FROM DATABASE:\n{order_data_text}\n"
                        logger.info(f"✅ Retrieved order data for {order_id}")
                else:
                    logger.warning(f"⚠️ No order data returned for {order_id}")
            except Exception as e:
                logger.error(f"❌ Error calling MCP tool: {e}")
                import traceback
                traceback.print_exc()
        
        # Enhance user message with order context
        enhanced_message = user_message
        if order_context:
            # Parse and format order data more explicitly
            try:
                order_data = json.loads(order_context.split("ORDER DATA FROM DATABASE:\n")[1])
                enhanced_message = f"""{user_message}

ORDER INFORMATION:
- Order ID: {order_data.get('order_id', 'N/A')}
- Product: {order_data.get('product_name', 'N/A')}
- Category: {order_data.get('category', 'N/A')}
- Delivery Date: {order_data.get('delivery_date', 'N/A')}
- Price: ${order_data.get('price', 'N/A')}
- Opened: {order_data.get('is_opened', 'N/A')}

Use this order information to determine return eligibility."""
                logger.info(f"📦 Formatted order data: Category={order_data.get('category')}, Delivery={order_data.get('delivery_date')}")
            except:
                # Fallback to original format
                enhanced_message = f"""{user_message}

{order_context}

IMPORTANT: Use the EXACT data from above."""
        
        # Build tools list
        tools = []
        
        # Add file_search tool if vector store exists
        vector_store_id = get_or_create_vector_store()
        if vector_store_id:
            tools.append({
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
                "max_num_results": 5,
            })
            logger.info(f"✅ Added file_search tool (vector_store: {vector_store_id})")
        
        # Only add MCP tool if we didn't pre-fetch order data
        # This prevents duplicate MCP calls
        if not order_context:
            tools.append({
                "type": "mcp",
                "server_label": "TechMartOrdersServer",
                "server_url": MCP_SERVER_URL,
            })
            logger.info(f"✅ Added MCP tool (server: {MCP_SERVER_URL})")
        else:
            logger.info(f"ℹ️  Skipping MCP tool (order data already fetched)")
        
        # Create response using Llama Stack
        logger.info("🔄 Sending request to Llama Stack...")
        start_time = datetime.now()
        
        # Determine tool choice based on available tools
        # If we have order data: only use file_search
        # If no order data but order query: allow MCP tool
        # For general queries: force file_search only
        if order_context:
            # We already have order data, only need policy from file_search
            tool_choice_param = {"type": "file_search"} if vector_store_id else None
        elif order_id:
            # Order query but no data yet, allow MCP tool
            tool_choice_param = "required"
        else:
            # General policy query
            tool_choice_param = {"type": "file_search"} if vector_store_id else None
        
        query_type = "Order with data" if order_context else ("Order query" if order_id else "General policy")
        logger.info(f"🔧 Query type: {query_type}")
        logger.info(f"🔧 Tool choice: {tool_choice_param}")
        
        response = client.with_options(timeout=600.0).responses.create(
            model=MODEL_ID,
            input=enhanced_message,  # Use enhanced message with order data
            stream=False,
            max_tool_calls=5,  # Increased to allow multiple tool calls
            instructions=INSTRUCTIONS,
            tools=tools,
            tool_choice=tool_choice_param,
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Received response from Llama Stack ({elapsed:.2f}s)")
        
        # Log detailed response structure for debugging
        logger.info(f"📊 Response type: {type(response)}")
        logger.info(f"📊 Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
        
        # Try to extract and log tool execution information
        if hasattr(response, 'output'):
            logger.info(f"🔧 Response output type: {type(response.output)}")
            if hasattr(response.output, 'tool_calls'):
                logger.info(f"🔧 Tool calls found: {len(response.output.tool_calls)}")
                for i, tool_call in enumerate(response.output.tool_calls, 1):
                    logger.info(f"   {i}. Tool: {tool_call.tool_name if hasattr(tool_call, 'tool_name') else 'unknown'}")
            else:
                logger.info("🔧 No tool_calls attribute in response.output")
        
        # Extract response text with better handling for both vLLM and Ollama
        bot_response = ""
        
        # Try multiple ways to extract the response (cascading fallback)
        if hasattr(response, 'output_text') and response.output_text:
            # vLLM format (checked first for backward compatibility)
            bot_response = response.output_text
            logger.info("✅ Extracted from output_text (vLLM format)")
        elif hasattr(response, 'text') and response.text:
            # Alternative text attribute
            bot_response = response.text
            logger.info("✅ Extracted from text attribute")
        elif hasattr(response, 'output'):
            # Handle Ollama's list-based output format
            if isinstance(response.output, list):
                # Extract text from list of message objects
                for item in response.output:
                    if isinstance(item, dict):
                        if 'content' in item:
                            bot_response += str(item['content']) + "\n"
                        elif 'text' in item:
                            bot_response += str(item['text']) + "\n"
                    elif hasattr(item, 'content'):
                        bot_response += str(item.content) + "\n"
                    elif hasattr(item, 'text'):
                        bot_response += str(item.text) + "\n"
                    else:
                        bot_response += str(item) + "\n"
                logger.info("✅ Extracted from output list (Ollama format)")
            elif isinstance(response.output, str):
                bot_response = response.output
                logger.info("✅ Extracted from output string")
            else:
                bot_response = str(response.output) if response.output else ""
                logger.info("✅ Extracted from output (converted to string)")
        else:
            # Fallback: convert entire response to string
            bot_response = str(response)
            logger.info("⚠️ Fallback: converted entire response to string")
        
        # Clean up the response
        bot_response = bot_response.strip()
        
        logger.info(f"📤 Response length: {len(bot_response)} characters")
        
        # Log if response is empty
        if not bot_response or len(bot_response.strip()) == 0:
            logger.warning("⚠️  Empty response generated!")
            logger.warning(f"Response object: {response}")
            bot_response = "Error: No response generated. Please try again."
        
        # Log response object structure for debugging
        logger.debug(f"Response object type: {type(response)}")
        logger.debug(f"Response attributes: {dir(response)}")
        
        return jsonify({
            'response': bot_response,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload/rag', methods=['POST'])
def upload_rag_document():
    """Upload a document for RAG (vector store)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        logger.info(f"Uploading RAG document: {file.filename}")
        
        # Get or create vector store
        vector_store_id = get_or_create_vector_store()
        if not vector_store_id:
            return jsonify({'error': 'Failed to create vector store'}), 500
        
        # Upload file to Llama Stack
        file_info = client.files.create(
            file=(file.filename, file.stream),
            purpose="assistants",  # API only accepts "assistants" or "batch"
        )
        
        logger.info(f"✅ Uploaded file: {file_info.id}")
        
        # Add file to vector store with chunking strategy
        vector_store_file = client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_info.id,
            chunking_strategy={
                "type": "static",
                "static": {
                    "max_chunk_size_tokens": 400,
                    "chunk_overlap_tokens": 100,
                },
            },
        )
        
        logger.info(f"✅ Added file to vector store: {file.filename}")
        
        return jsonify({
            'success': True,
            'message': f'Document "{file.filename}" uploaded successfully to RAG',
            'filename': file.filename,
            'file_id': file_info.id
        })
        
    except Exception as e:
        logger.error(f"❌ Error uploading RAG document: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload/mcp', methods=['POST'])
def upload_mcp_data():
    """Upload CSV data for MCP server and save to IBM i DB2 database"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are supported'}), 400
        
        logger.info(f"Uploading MCP data: {file.filename}")
        
        # Read CSV file
        file_content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(file_content))
        orders = list(csv_reader)
        
        # Connect to IBM i DB2 database via ODBC
        import pyodbc
        conn_str = (
            f"DRIVER={{IBM i Access ODBC Driver}};"
            f"SYSTEM={DB_SYSTEM};"
            f"UID={DB_USER};"
            f"PWD={DB_PASSWORD};"
            f"DBQ={DB_SCHEMA};"
        )
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist (DB2 syntax)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.ORDERS (
                ORDER_ID VARCHAR(50) NOT NULL PRIMARY KEY,
                CUSTOMER_EMAIL VARCHAR(255),
                PRODUCT_NAME VARCHAR(255),
                CATEGORY VARCHAR(100),
                PRICE DECIMAL(10,2),
                ORDER_DATE DATE,
                DELIVERY_DATE DATE,
                STATUS VARCHAR(50),
                IS_OPENED VARCHAR(10)
            )
        """)
        
        # Insert or update orders (DB2 MERGE syntax)
        row_count = 0
        for row in orders:
            # Handle both 'category' and 'product_category' column names
            category = row.get('category', row.get('product_category', 'General'))
            
            # DB2 uses MERGE for upsert operations
            cursor.execute(f"""
                MERGE INTO {DB_SCHEMA}.ORDERS AS target
                USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)) AS source (
                    ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, CATEGORY,
                    PRICE, ORDER_DATE, DELIVERY_DATE, STATUS, IS_OPENED
                )
                ON target.ORDER_ID = source.ORDER_ID
                WHEN MATCHED THEN
                    UPDATE SET
                        CUSTOMER_EMAIL = source.CUSTOMER_EMAIL,
                        PRODUCT_NAME = source.PRODUCT_NAME,
                        CATEGORY = source.CATEGORY,
                        PRICE = source.PRICE,
                        ORDER_DATE = source.ORDER_DATE,
                        DELIVERY_DATE = source.DELIVERY_DATE,
                        STATUS = source.STATUS,
                        IS_OPENED = source.IS_OPENED
                WHEN NOT MATCHED THEN
                    INSERT (ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, CATEGORY,
                            PRICE, ORDER_DATE, DELIVERY_DATE, STATUS, IS_OPENED)
                    VALUES (source.ORDER_ID, source.CUSTOMER_EMAIL,
                            source.PRODUCT_NAME, source.CATEGORY,
                            source.PRICE, source.ORDER_DATE,
                            source.DELIVERY_DATE, source.STATUS,
                            source.IS_OPENED)
            """, (
                row['order_id'],
                row['customer_email'],
                row['product_name'],
                category,
                float(row['price']),
                row['order_date'],
                row['delivery_date'],
                row['status'],
                row['is_opened']
            ))
            row_count += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Saved {row_count} orders to PostgreSQL database")
        
        # Automatically trigger reload via Llama Stack (calls MCP reload_orders tool)
        reload_success = False
        reload_message = ""
        try:
            if client and MODEL_ID:
                logger.info("🔄 Triggering automatic reload of MCP data from database...")
                response = client.with_options(timeout=600.0).responses.create(
                    model=MODEL_ID,
                    input="Reload the orders data from the database",
                    stream=False,
                    max_tool_calls=5,
                    instructions="Call the reload_orders tool to refresh the MCP server data.",
                    tools=[{
                        "type": "mcp",
                        "server_label": "TechMartOrdersServer",
                        "server_url": MCP_SERVER_URL,
                    }],
                )
                reload_message = response.output_text if hasattr(response, 'output_text') else "Reload triggered"
                reload_success = True
                logger.info(f"✅ Auto-reload completed: {reload_message}")
        except Exception as reload_error:
            logger.warning(f"⚠️ Auto-reload failed (manual reload may be needed): {reload_error}")
            reload_message = f"Auto-reload failed: {str(reload_error)}"
        
        return jsonify({
            'success': True,
            'message': f'CSV file "{file.filename}" saved to database and {"reloaded" if reload_success else "ready"}',
            'filename': file.filename,
            'rows': row_count,
            'saved_to': 'PostgreSQL Database',
            'auto_reload': reload_success,
            'reload_message': reload_message,
            'note': 'Data saved to PostgreSQL. ' + ('Data automatically reloaded!' if reload_success else 'Ask AI to reload: "Reload the orders data"')
        })
        
    except Exception as e:
        logger.error(f"❌ Error uploading MCP data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Check system status"""
    try:
        llama_stack_status = "connected" if client else "disconnected"
        
        # Try to ping MCP server (use local URL since UI runs on host)
        mcp_status = "unknown"
        try:
            # Try to connect to the MCP server SSE endpoint
            # Use MCP_SERVER_URL_LOCAL for health check since UI runs on host
            response = requests.get(MCP_SERVER_URL_LOCAL, timeout=10, stream=True)
            
            logger.info(f"MCP status check - Status: {response.status_code}, Content-Type: {response.headers.get('content-type', 'N/A')}")
            
            # Check if server is responding with valid SSE endpoint
            if response.status_code == 200 or 'text/event-stream' in response.headers.get('content-type', ''):
                mcp_status = "connected"
                logger.info("✅ MCP Server detected as connected")
            else:
                mcp_status = "error"
                logger.warning(f"⚠️ MCP Server returned unexpected response")
        except Exception as e:
            logger.error(f"❌ MCP status check failed: {e}")
            mcp_status = "disconnected"
        
        return jsonify({
            'llama_stack': {
                'status': llama_stack_status,
                'url': LLAMA_STACK_URL
            },
            'mcp_server': {
                'status': mcp_status,
                'url': MCP_SERVER_URL_LOCAL,  # Show local URL in status
                'container_url': MCP_SERVER_URL  # Show container URL for reference
            },
            'model_id': MODEL_ID,
            'vector_store_id': VECTOR_STORE_ID
        })
    except Exception as e:
        logger.error(f"❌ Error checking status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all uploaded files in the vector store"""
    try:
        vector_store_id = get_or_create_vector_store()
        if not vector_store_id:
            return jsonify({'files': []})
        
        # Get files from vector store
        vector_store_files = client.vector_stores.files.list(vector_store_id=vector_store_id)
        
        files_list = []
        for vsf in vector_store_files:
            try:
                # VectorStoreFile object has 'id' not 'file_id'
                file_id = vsf.id if hasattr(vsf, 'id') else None
                if not file_id:
                    continue
                    
                # Get file details
                file_info = client.files.retrieve(file_id)
                files_list.append({
                    'id': file_info.id,
                    'filename': file_info.filename if hasattr(file_info, 'filename') else 'Unknown',
                    'size': file_info.bytes if hasattr(file_info, 'bytes') else 0,
                    'created_at': file_info.created_at if hasattr(file_info, 'created_at') else None,
                    'status': vsf.status if hasattr(vsf, 'status') else 'completed'
                })
            except Exception as e:
                logger.warning(f"Could not retrieve file: {e}")
                continue
        
        return jsonify({'files': files_list})
        
    except Exception as e:
        logger.error(f"❌ Error listing files: {e}")
        return jsonify({'files': []})
@app.route('/api/files/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Delete a file from the vector store"""
    try:
        vector_store_id = get_or_create_vector_store()
        if not vector_store_id:
            return jsonify({'error': 'Vector store not found'}), 404
        
        # Delete file from vector store
        client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
        
        # Delete the file itself
        client.files.delete(file_id)
        
        logger.info(f"✅ Deleted file: {file_id}")
        return jsonify({'success': True, 'message': f'File {file_id} deleted'})
        
    except Exception as e:
        logger.error(f"❌ Error deleting file {file_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cleanup/policy-data', methods=['POST'])
def cleanup_policy_data():
    """Clean up all policy-related data from vector stores and OpenSearch"""
    try:
        if not client:
            return jsonify({'error': 'Llama Stack client not initialized'}), 500
        
        logger.info("🧹 Starting policy data cleanup...")
        cleanup_results = {
            'deleted_files': [],
            'deleted_vector_stores': [],
            'opensearch_indices': [],
            'errors': []
        }
        
        # Step 1: Clean up Llama Stack vector stores
        try:
            logger.info("📋 Listing all vector stores...")
            vector_stores = client.vector_stores.list()
            
            for vs in vector_stores:
                logger.info(f"🗑️  Processing vector store: {vs.name} ({vs.id})")
                
                try:
                    # List and delete all files in the vector store
                    files = client.vector_stores.files.list(vector_store_id=vs.id)
                    
                    for file in files:
                        try:
                            file_id = file.id if hasattr(file, 'id') else None
                            if file_id:
                                logger.info(f"   🗑️  Deleting file: {file_id}")
                                client.vector_stores.files.delete(
                                    vector_store_id=vs.id,
                                    file_id=file_id
                                )
                                # Also delete the file itself
                                try:
                                    client.files.delete(file_id)
                                    cleanup_results['deleted_files'].append(file_id)
                                    logger.info(f"   ✅ Deleted file: {file_id}")
                                except Exception as e:
                                    logger.warning(f"   ⚠️  Could not delete file {file_id}: {e}")
                                    cleanup_results['errors'].append(f"File {file_id}: {str(e)}")
                        except Exception as e:
                            logger.warning(f"   ⚠️  Error deleting file: {e}")
                            cleanup_results['errors'].append(f"File deletion: {str(e)}")
                    
                    # Delete the vector store
                    logger.info(f"   🗑️  Deleting vector store: {vs.id}")
                    client.vector_stores.delete(vs.id)
                    cleanup_results['deleted_vector_stores'].append({
                        'id': vs.id,
                        'name': vs.name
                    })
                    logger.info(f"   ✅ Deleted vector store: {vs.name}")
                    
                except Exception as e:
                    logger.error(f"   ❌ Error processing vector store {vs.id}: {e}")
                    cleanup_results['errors'].append(f"Vector store {vs.id}: {str(e)}")
            
            # Clear the cached vector store ID
            global VECTOR_STORE_ID
            VECTOR_STORE_ID = None
            logger.info("✅ Cleared cached vector store ID")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up Llama Stack: {e}")
            cleanup_results['errors'].append(f"Llama Stack: {str(e)}")
        
        # Step 2: Clean up OpenSearch indices
        try:
            opensearch_url = os.environ.get('OPENSEARCH_URL', 'http://localhost:9200')
            opensearch_user = os.environ.get('OPENSEARCH_USER', 'admin')
            opensearch_password = os.environ.get('OPENSEARCH_PASSWORD', 'admin')
            
            logger.info("🔍 Cleaning up OpenSearch indices...")
            
            # Get all indices
            response = requests.get(
                f"{opensearch_url}/_cat/indices?format=json",
                auth=(opensearch_user, opensearch_password),
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                indices = response.json()
                vs_indices = [idx for idx in indices if idx['index'].startswith('vs_')]
                
                for idx in vs_indices:
                    index_name = idx['index']
                    logger.info(f"🗑️  Deleting OpenSearch index: {index_name}")
                    
                    delete_response = requests.delete(
                        f"{opensearch_url}/{index_name}",
                        auth=(opensearch_user, opensearch_password),
                        verify=False,
                        timeout=10
                    )
                    
                    if delete_response.status_code in [200, 404]:
                        cleanup_results['opensearch_indices'].append(index_name)
                        logger.info(f"✅ Deleted OpenSearch index: {index_name}")
                    else:
                        logger.warning(f"⚠️  Failed to delete index {index_name}")
                        cleanup_results['errors'].append(f"OpenSearch index {index_name}: HTTP {delete_response.status_code}")
            else:
                logger.warning(f"⚠️  Could not list OpenSearch indices: HTTP {response.status_code}")
                cleanup_results['errors'].append(f"OpenSearch list: HTTP {response.status_code}")
                
        except Exception as e:
            logger.warning(f"⚠️  Error cleaning up OpenSearch: {e}")
            cleanup_results['errors'].append(f"OpenSearch: {str(e)}")
        
        # Prepare response
        success = len(cleanup_results['deleted_vector_stores']) > 0 or len(cleanup_results['opensearch_indices']) > 0
        
        logger.info("✅ Policy data cleanup completed")
        
        return jsonify({
            'success': success,
            'message': 'Policy data cleanup completed',
            'results': {
                'files_deleted': len(cleanup_results['deleted_files']),
                'vector_stores_deleted': len(cleanup_results['deleted_vector_stores']),
                'opensearch_indices_deleted': len(cleanup_results['opensearch_indices']),
                'errors': cleanup_results['errors']
            },
            'details': cleanup_results
        })
        
    except Exception as e:
        logger.error(f"❌ Error in cleanup endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    """Clear the current chat session"""
    try:
        if 'session_id' in session:
            old_session = session['session_id']
            session.pop('session_id')
            logger.info(f"Cleared session: {old_session}")
        
        return jsonify({
            'success': True,
            'message': 'Session cleared successfully'
        })
    except Exception as e:
        logger.error(f"❌ Error clearing session: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)

# Made with Bob

"""
TechMart Customer Service Assistant - Web UI
Integrates with OGX (RAG + MCP) for intelligent customer support
"""

from flask import Flask, render_template, request, jsonify, session
from ogx_client import OgxClient
import os
import uuid
import logging
from datetime import datetime
import requests
import csv
import io
import psycopg2
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'techmart-demo-secret-key-change-in-production')

# Configuration
OGX_URL = os.environ.get('OGX_URL', 'http://localhost:8321')
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:9001/sse')

# Database configuration
# Use host.containers.internal for containers to reach host PostgreSQL
# Use localhost for local Python execution
DB_HOST = os.environ.get('DB_HOST', 'host.containers.internal')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'techmart')
DB_USER = os.environ.get('DB_USER', 'techmart')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'techmart123')

# Universal instruction for all scenarios
INSTRUCTIONS = """You are a helpful and professional customer service assistant.

WORKFLOW:
1. Analyze the customer's question carefully
2. Use available tools to gather all necessary information
3. After gathering information, provide a COMPLETE, well-structured answer

RESPONSE REQUIREMENTS:
- Be clear, accurate, and professional
- Include all relevant details from the tools
- Structure your answer logically
- Provide actionable next steps when applicable
- Never stop after calling tools - always synthesize the final answer

IMPORTANT: You MUST provide a final answer after using tools. Be helpful, accurate, and thorough."""

# Initialize OGX client
try:
    client = OgxClient(base_url=OGX_URL)
    logger.info(f"✅ Connected to OGX at {OGX_URL}")
    
    # Extract LLM model ID dynamically
    # .list() returns a SyncPage; use .data to get the list of model objects
    models = client.models.list().data
    llm_model = next((m for m in models if m.model_type == "llm"), None)
    
    if not llm_model:
        logger.error("❌ No LLM model found in OGX")
        raise RuntimeError("No LLM model available")
    
    MODEL_ID = llm_model.identifier
    logger.info(f"✅ Using LLM model: {MODEL_ID}")
        
except Exception as e:
    logger.error(f"❌ Failed to initialize OGX: {e}")
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
        models = client.models.list().data
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
                "provider_id": "faiss",
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
            return jsonify({'error': 'OGX client not initialized'}), 500
        
        logger.info(f"Processing message: {user_message[:50]}...")
        
        # Build tools list
        tools = []
        
        # Add file_search tool if vector store exists
        vector_store_id = get_or_create_vector_store()
        if vector_store_id:
            tools.append({
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
            })
        
        # Add MCP tool
        tools.append({
            "type": "mcp",
            "server_label": "TechMartOrdersServer",
            "server_url": MCP_SERVER_URL,
        })
        
        # Create response using OGX
        response = client.with_options(timeout=600.0).responses.create(
            model=MODEL_ID,
            input=user_message,
            stream=False,
            max_tool_calls=10,
            instructions=INSTRUCTIONS,
            tools=tools,
        )
        
        # Extract response text
        bot_response = response.output_text if hasattr(response, 'output_text') else str(response)
        
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
        
        # Upload file to OGX
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
    """Upload CSV data for MCP server and save to PostgreSQL database"""
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
        
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Prepare data for insertion
        order_data = []
        for row in orders:
            # Handle both 'category' and 'product_category' column names
            category = row.get('category', row.get('product_category', 'General'))
            
            order_data.append((
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
        
        # Insert orders (upsert - update if exists)
        insert_query = """
            INSERT INTO orders (
                order_id, customer_email, product_name, category,
                price, order_date, delivery_date, status, is_opened
            ) VALUES %s
            ON CONFLICT (order_id) DO UPDATE SET
                customer_email = EXCLUDED.customer_email,
                product_name = EXCLUDED.product_name,
                category = EXCLUDED.category,
                price = EXCLUDED.price,
                order_date = EXCLUDED.order_date,
                delivery_date = EXCLUDED.delivery_date,
                status = EXCLUDED.status,
                is_opened = EXCLUDED.is_opened
        """
        execute_values(cursor, insert_query, order_data)
        conn.commit()
        
        row_count = len(orders)
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Saved {row_count} orders to PostgreSQL database")
        
        # Automatically trigger reload via OGX (calls MCP reload_orders tool)
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
        ogx_stack_status = "connected" if client else "disconnected"
        
        # Try to ping MCP server
        mcp_status = "unknown"
        try:
            # Try to connect to the MCP server SSE endpoint
            # SSE endpoints return 200 with text/event-stream content-type
            response = requests.get(MCP_SERVER_URL, timeout=10, stream=True)
            
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
            'ogx_stack': {
                'status': ogx_stack_status,
                'url': OGX_URL
            },
            'mcp_server': {
                'status': mcp_status,
                'url': MCP_SERVER_URL
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
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)

# Made with Bob

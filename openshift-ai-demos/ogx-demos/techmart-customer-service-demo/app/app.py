"""
TechMart Customer Service Assistant - Web UI
Integrates with OGX (RAG + MCP) for intelligent customer support
"""

from flask import Flask, render_template, request, jsonify, session
from ogx_client import OgxClient
import os
import re
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'techmart-demo-secret-key-change-in-production')

# Limit uploaded files to 5 MB to prevent blocking the server on large uploads.
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Configuration
OGX_URL = os.environ.get('OGX_URL', 'http://localhost:8321')
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:9001/sse')

# Universal instruction for all scenarios
INSTRUCTIONS = """You are a helpful TechMart customer service assistant.

Today's date is April 21, 2024. Use this exact date as "now" for every date
calculation (days remaining, whether a return window has expired). Never assume
any other date.

CRITICAL — GROUNDING RULES (apply to every answer):
- For ANY question about policy — shipping times, delivery, returns, refunds,
  restocking fees, warranties, gift returns, etc. — you MUST first use the
  file_search tool to retrieve the relevant text from the policy document, and
  base your answer ONLY on that retrieved text.
- For questions about a specific order, use the get_order tool.
- Use ONLY facts from retrieved policy text or order tool results. Never guess,
  assume, or invent details such as day ranges, fees, or dates. If the retrieved
  policy does not contain the answer, say you don't have that information rather
  than making something up.
- Quote the policy's exact numbers (e.g. shipping "3-5 business days"); do not
  paraphrase them into different ranges.

=== HOW TO ANSWER A RETURN ELIGIBILITY QUESTION ===
Before writing your answer, work through these steps IN ORDER inside a section
that starts with "Reasoning:". Do the math carefully, one line per step:

1. Order facts (from the get_order tool): category, delivery_date, price,
   is_opened.
2. Return window: read the number of days for THIS item's exact category from
   the policy (electronics and standard items have different windows). Write it
   as "window = N days".
3. Deadline = delivery_date + window. Compute the actual calendar date.
4. Days remaining = deadline − today (April 21, 2024). If deadline is on or
   after today, the item is ELIGIBLE; otherwise NOT eligible.
5. Restocking fee: if is_opened is false, the fee is 0%. If is_opened is true,
   read the restocking fee percentage for THIS item's exact category from the
   policy's "Restocking Fees" section. NEVER use the 20% missing-accessories
   number or any other condition-based deduction unless the customer explicitly
   says accessories are missing or the item is damaged. The restocking fee
   applies because the item is opened, not because of timing.
6. Fee amount = price × fee%. Refund = price − fee amount. Show the arithmetic.

=== THEN WRITE THE FINAL ANSWER ===
After the reasoning section, write "Answer:" followed by 2-3 sentences maximum
that state: yes/no, the deadline and days remaining, and (if opened) the
restocking fee percentage, fee amount, and refund. No step-by-step instructions,
contact info, or warnings unless specifically asked.

For non-return questions, skip the reasoning section and just answer directly and
concisely (2-3 sentences), always giving a final answer after using tools."""

def _strip_special_tokens(text: str) -> str:
    """Remove chat-template special tokens that can leak into the output.

    Some models emit delimiter tokens such as ``<|...|>`` (channel markers, stop
    tokens, or trailing IDs) that should never be shown to the customer.
    """
    return re.sub(r"<\|[^|]*\|>", "", text).strip()


def _extract_final_answer(text: str) -> str:
    """Return only the customer-facing answer, dropping any 'Reasoning:' section.

    The model is prompted to think under a 'Reasoning:' heading and then write
    the reply under 'Answer:'. We show only the text after the last 'Answer:'.
    If no such heading is present (e.g. non-return questions), return the text
    unchanged. Any leaked special tokens are stripped from the result.
    """
    marker = "answer:"
    lower = text.lower()
    idx = lower.rfind(marker)
    if idx != -1:
        text = text[idx + len(marker):]
    return _strip_special_tokens(text)


# Helpers to handle model items that may be typed objects or raw tuples
def _model_type(m):
    if isinstance(m, tuple):
        return m[1] if len(m) > 1 else None
    return getattr(m, 'model_type', None)

def _model_id(m):
    if isinstance(m, tuple):
        return m[0]
    return getattr(m, 'identifier', None)

# Initialize OGX client
try:
    client = OgxClient(base_url=OGX_URL)
    logger.info(f"✅ Connected to OGX at {OGX_URL}")

    # Extract LLM model ID dynamically
    # .list() may return a SyncPage (.data) or a plain iterable of tuples/objects
    models_response = client.models.list()
    models = models_response.data if hasattr(models_response, 'data') else list(models_response)
    llm_model = next((m for m in models if _model_type(m) == "llm"), None)
    
    if not llm_model:
        logger.error("❌ No LLM model found in OGX")
        raise RuntimeError("No LLM model available")
    
    MODEL_ID = _model_id(llm_model)
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

    if not client:
        return None

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
        models_response = client.models.list()
        models = models_response.data if hasattr(models_response, 'data') else list(models_response)
        embedding_model = next((m for m in models if _model_type(m) == "embedding"), None)

        if not embedding_model:
            logger.error("No embedding model found")
            return None

        embedding_model_id = _model_id(embedding_model)
        embedding_dimension = int(
            embedding_model.metadata.get("embedding_dimension", 384)
            if hasattr(embedding_model, 'metadata')
            else 384
        )
        
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

        # The model is instructed to think step by step under a "Reasoning:"
        # heading and then give the customer-facing reply under "Answer:". Show
        # only the final answer in the UI, dropping the internal reasoning.
        bot_response = _extract_final_answer(bot_response)

        return jsonify({
            'response': bot_response,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"❌ Error in chat endpoint: {e}")
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
                    # Larger chunks keep each policy section (e.g. the full
                    # Restocking Fees or Return Time Limits block) intact so the
                    # right numbers are retrieved together instead of split
                    # across chunks.
                    "max_chunk_size_tokens": 800,
                    "chunk_overlap_tokens": 150,
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
        logger.exception(f"❌ Error uploading RAG document: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Check system status.

    The app itself never calls the MCP server — OGX invokes MCP tools in-cluster —
    so the app's reachability to MCP is not a meaningful health signal and is not
    reported here.
    """
    try:
        ogx_stack_status = "connected" if client else "disconnected"

        return jsonify({
            'ogx_stack': {
                'status': ogx_stack_status,
                'url': OGX_URL
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
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

# Made with Bob

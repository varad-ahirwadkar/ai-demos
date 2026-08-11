"""
Intelligent Document Q&A System using RH OpenShift Llama Stack
A production-ready RAG application with FAISS vector store and Llama models
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import PyPDF2
from llama_stack_client import LlamaStackClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
LLAMA_STACK_URL = os.getenv('LLAMA_STACK_URL', 'http://techmart-ogx-service.llama.svc.cluster.local:8321')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/uploads')
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 1000))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', 200))
MAX_CHUNKS = int(os.getenv('MAX_CHUNKS', 5))

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md'}

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app)

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Llama Stack client
try:
    client = LlamaStackClient(base_url=LLAMA_STACK_URL)
    logger.info(f"Connected to Llama Stack at {LLAMA_STACK_URL}")
except Exception as e:
    logger.error(f"Failed to connect to Llama Stack: {e}")
    client = None

# Global state (in production, use Redis or database)
documents_store = {}
vector_store_id = None
embedding_model_id = None
llm_model_id = None


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += f"\n[Page {page_num + 1}]\n{page_text}"
            return text
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
        raise


def extract_text_from_file(file_path: str, filename: str) -> str:
    """Extract text from uploaded file"""
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ['txt', 'md']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at sentence boundary
        if end < text_length:
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            
            if break_point > chunk_size * 0.5:  # Only break if we're past halfway
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1
        
        chunks.append(chunk.strip())
        start = end - overlap
    
    return [c for c in chunks if c]  # Remove empty chunks


def initialize_models():
    """Initialize and cache model IDs"""
    global embedding_model_id, llm_model_id, vector_store_id
    
    if not client:
        raise RuntimeError("Llama Stack client not initialized")
    
    try:
        # Get available models
        models = client.models.list()
        logger.info(f"Found {len(models)} models")
        
        # Find embedding model
        embedding_models = [m for m in models if m.model_type == "embedding"]
        if not embedding_models:
            raise RuntimeError("No embedding models found")
        embedding_model = embedding_models[0]
        embedding_model_id = embedding_model.identifier
        embedding_dimension = int(embedding_model.metadata.get("embedding_dimension", 768))
        
        # Find LLM model
        llm_models = [m for m in models if m.model_type == "llm"]
        if not llm_models:
            raise RuntimeError("No LLM models found")
        llm_model_id = llm_models[0].identifier
        
        logger.info(f"Using embedding model: {embedding_model_id}")
        logger.info(f"Using LLM model: {llm_model_id}")
        
        # Create or get vector store
        try:
            vector_store = client.vector_stores.create(
                name=f"doc_qa_store_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                extra_body={
                    "embedding_model": embedding_model_id,
                    "embedding_dimension": embedding_dimension,
                    "provider_id": "faiss",
                }
            )
            vector_store_id = vector_store.id
            logger.info(f"Created vector store: {vector_store_id}")
        except Exception as e:
            logger.warning(f"Could not create vector store: {e}")
            # Try to list existing stores
            try:
                stores = client.vector_stores.list()
                if stores:
                    vector_store_id = stores[0].id
                    logger.info(f"Using existing vector store: {vector_store_id}")
            except:
                pass
        
        return True
    except Exception as e:
        logger.error(f"Error initializing models: {e}")
        return False


@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    status = {
        'status': 'healthy',
        'llama_stack_connected': client is not None,
        'models_initialized': embedding_model_id is not None and llm_model_id is not None,
        'vector_store_ready': vector_store_id is not None,
        'documents_count': len(documents_store)
    }
    return jsonify(status)


@app.route('/upload', methods=['POST'])
def upload_document():
    """Upload and process a document"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    try:
        # Initialize models if needed
        if not embedding_model_id:
            if not initialize_models():
                return jsonify({'error': 'Failed to initialize models'}), 500
        
        # Save file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Extract text
        logger.info(f"Processing file: {filename}")
        text = extract_text_from_file(file_path, filename)
        
        # Create chunks
        chunks = chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks from {filename}")
        
        # Generate document ID
        doc_id = hashlib.md5(f"{filename}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        # Store document metadata
        documents_store[doc_id] = {
            'id': doc_id,
            'name': filename,
            'chunks': len(chunks),
            'uploaded_at': datetime.now().isoformat(),
            'text': text[:500] + '...' if len(text) > 500 else text
        }
        
        # Add chunks to vector store
        if vector_store_id:
            try:
                for i, chunk in enumerate(chunks):
                    # In production, batch these operations
                    client.vector_stores.add_chunks(
                        vector_store_id=vector_store_id,
                        chunks=[{
                            'content': chunk,
                            'metadata': {
                                'document_id': doc_id,
                                'chunk_index': i,
                                'filename': filename
                            }
                        }]
                    )
                logger.info(f"Added {len(chunks)} chunks to vector store")
            except Exception as e:
                logger.error(f"Error adding chunks to vector store: {e}")
                # Continue anyway, we have the chunks stored
        
        # Clean up file
        os.remove(file_path)
        
        return jsonify({
            'status': 'success',
            'document_id': doc_id,
            'filename': filename,
            'chunks_created': len(chunks),
            'message': f'Successfully processed {filename}'
        })
        
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/ask', methods=['POST'])
def ask_question():
    """Ask a question about uploaded documents"""
    data = request.get_json()
    
    if not data or 'question' not in data:
        return jsonify({'error': 'No question provided'}), 400
    
    question = data['question']
    document_id = data.get('document_id')
    max_results = data.get('max_results', MAX_CHUNKS)
    
    try:
        # Initialize models if needed
        if not embedding_model_id or not llm_model_id:
            if not initialize_models():
                return jsonify({'error': 'Failed to initialize models'}), 500
        
        # Search vector store
        relevant_chunks = []
        if vector_store_id:
            try:
                search_results = client.vector_stores.search(
                    vector_store_id=vector_store_id,
                    query=question,
                    limit=max_results
                )
                relevant_chunks = [
                    {
                        'text': result.content,
                        'score': result.score,
                        'metadata': result.metadata
                    }
                    for result in search_results
                ]
            except Exception as e:
                logger.error(f"Error searching vector store: {e}")
        
        # Build context from relevant chunks
        context = "\n\n".join([
            f"[Source {i+1}] {chunk['text']}"
            for i, chunk in enumerate(relevant_chunks)
        ])
        
        # Generate answer using LLM
        prompt = f"""Based on the following context, answer the question. If the answer cannot be found in the context, say so.

Context:
{context}

Question: {question}

Answer:"""
        
        response = client.inference.chat_completion(
            model_id=llm_model_id,
            messages=[
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        
        answer = response.completion_message.content
        
        return jsonify({
            'answer': answer,
            'sources': relevant_chunks,
            'model': llm_model_id,
            'question': question
        })
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/documents', methods=['GET'])
def list_documents():
    """List all uploaded documents"""
    return jsonify({
        'documents': list(documents_store.values()),
        'count': len(documents_store)
    })


@app.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a document"""
    if doc_id not in documents_store:
        return jsonify({'error': 'Document not found'}), 404
    
    del documents_store[doc_id]
    return jsonify({'status': 'success', 'message': 'Document deleted'})


if __name__ == '__main__':
    # Initialize on startup
    if client:
        initialize_models()
    
    # Run the app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'false').lower() == 'true')

# Made with Bob

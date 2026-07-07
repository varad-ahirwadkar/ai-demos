"""
TechMart Customer Service Assistant
Demonstrates RAG + MCP integration with Llama Stack
"""

from flask import Flask, render_template, request, jsonify
import os
import logging
from typing import Optional
import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
LLAMA_STACK_URL = os.getenv("LLAMA_STACK_URL", "http://localhost:5001")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:9001/sse")

# Determine data path (handle both development and container environments)
if os.path.exists('return-policy.txt'):
    POLICY_PATH = 'return-policy.txt'
elif os.path.exists('../data/return-policy.txt'):
    POLICY_PATH = '../data/return-policy.txt'
else:
    POLICY_PATH = 'data/return-policy.txt'

class TechMartAssistant:
    """Customer service assistant with RAG + MCP capabilities"""
    
    def __init__(self):
        self.policy_content = self._load_policy()
        
    def _load_policy(self) -> str:
        """Load return policy document"""
        try:
            with open(POLICY_PATH, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"return-policy.txt not found at {POLICY_PATH}")
            return ""
    
    async def get_order_details(self, order_id: str) -> Optional[dict]:
        """Get order details from MCP server"""
        try:
            async with sse_client(MCP_SERVER_URL) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "get_order",
                        arguments={"order_id": order_id}
                    )
                    
                    if result and len(result.content) > 0:
                        return result.content[0].text
                    return None
        except Exception as e:
            logger.error(f"Error getting order details: {e}")
            return None
    
    async def check_return_eligibility(self, order_id: str) -> Optional[dict]:
        """Check return eligibility via MCP server"""
        try:
            async with sse_client(MCP_SERVER_URL) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        "check_return_eligibility",
                        arguments={"order_id": order_id}
                    )
                    
                    if result and len(result.content) > 0:
                        import json
                        return json.loads(result.content[0].text)
                    return None
        except Exception as e:
            logger.error(f"Error checking eligibility: {e}")
            return None
    
    def search_policy(self, query: str) -> str:
        """Simple keyword search in policy (RAG simulation)"""
        query_lower = query.lower()
        lines = self.policy_content.split('\n')
        
        relevant_lines = []
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['return', 'refund', 'restocking', 'electronics', 'days']):
                # Get context (line before and after)
                start = max(0, i-1)
                end = min(len(lines), i+2)
                relevant_lines.extend(lines[start:end])
        
        return '\n'.join(set(relevant_lines))
    
    async def answer_question(self, question: str) -> dict:
        """Answer customer question using RAG + MCP"""
        question_lower = question.lower()
        
        # Extract order ID if present
        order_id = None
        words = question.split()
        for word in words:
            if word.startswith('ORD-'):
                order_id = word.rstrip('?,.')
                break
        
        response = {
            "answer": "",
            "policy_context": "",
            "order_details": None,
            "eligibility": None
        }
        
        # Get policy context (RAG)
        policy_context = self.search_policy(question)
        response["policy_context"] = policy_context
        
        # Get order details if order ID mentioned (MCP)
        if order_id:
            order_details = await self.get_order_details(order_id)
            eligibility = await self.check_return_eligibility(order_id)
            
            response["order_details"] = order_details
            response["eligibility"] = eligibility
            
            # Generate answer
            if eligibility:
                answer = self._format_eligibility_response(order_id, order_details, eligibility, policy_context)
            else:
                answer = f"I found information about order {order_id}, but couldn't determine eligibility. Please contact support."
        else:
            # Policy-only question
            answer = self._format_policy_response(question, policy_context)
        
        response["answer"] = answer
        return response
    
    def _format_eligibility_response(self, order_id: str, order: str, eligibility: dict, policy: str) -> str:
        """Format response for return eligibility question"""
        import json
        
        try:
            order_data = json.loads(order) if isinstance(order, str) else order
        except:
            order_data = {}
        
        product_name = order_data.get('product_name', 'your item')
        delivery_date = order_data.get('delivery_date', 'unknown')
        price = order_data.get('price', 0)
        is_opened = order_data.get('is_opened', 'unknown')
        
        is_eligible = eligibility.get('is_eligible', False)
        days_since = eligibility.get('days_since_delivery', 0)
        days_remaining = eligibility.get('days_remaining', 0)
        restocking_fee = eligibility.get('restocking_fee_percent', 0)
        estimated_refund = eligibility.get('estimated_refund', 0)
        message = eligibility.get('message', '')
        
        if is_eligible:
            response = f"""✅ **Return Eligibility for Order {order_id}**

**Product**: {product_name}
**Delivery Date**: {delivery_date}
**Original Price**: ${price:.2f}

**Status**: ✓ Eligible for return
**Time**: {days_remaining} days remaining in return window
**Opened**: {'Yes' if is_opened == 'yes' else 'No'}

"""
            if restocking_fee > 0:
                response += f"""**Restocking Fee**: {restocking_fee}% (${price * restocking_fee / 100:.2f})
**Estimated Refund**: ${estimated_refund:.2f}

"""
            else:
                response += f"""**Restocking Fee**: None
**Estimated Refund**: ${estimated_refund:.2f}

"""
            
            response += """**Next Steps**:
1. Log into your TechMart account
2. Go to "My Orders"
3. Select this order
4. Click "Return Item"
5. Print the return label
6. Ship within 5 business days

**Note**: Refund will be processed within 5-7 business days after we receive the item."""
        
        else:
            response = f"""❌ **Return Not Available for Order {order_id}**

**Product**: {product_name}
**Delivery Date**: {delivery_date}
**Days Since Delivery**: {days_since}

**Status**: ✗ Not eligible for return
**Reason**: {message}

**Alternative Options**:
- Contact customer support for special circumstances
- Check if manufacturer warranty applies
- Consider exchange instead of return

**Support**: support@techmart.com | 1-800-TECHMART"""
        
        return response
    
    def _format_policy_response(self, question: str, policy: str) -> str:
        """Format response for policy-only questions"""
        if not policy:
            return "I don't have specific policy information for that question. Please contact support@techmart.com"
        
        response = f"""**TechMart Return Policy**

{policy}

**Need More Help?**
- Email: support@techmart.com
- Phone: 1-800-TECHMART
- Live Chat: Available 24/7 on our website"""
        
        return response

# Initialize assistant
assistant = TechMartAssistant()

@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/api/ask', methods=['POST'])
def ask_question():
    """Handle customer questions"""
    try:
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({"error": "No question provided"}), 400
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(assistant.answer_question(question))
        loop.close()
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "mcp_server": MCP_SERVER_URL,
        "policy_loaded": bool(assistant.policy_content)
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)

# Made with Bob

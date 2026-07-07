#!/usr/bin/env python3
"""Fix notebook to use universal instructions while preserving tools"""

import json
import re

# Read the notebook
with open('techmart-rag-mcp-demo.ipynb', 'r') as f:
    content = f.read()

# Replace timeout values
content = content.replace('timeout=60.0', 'timeout=120.0')

# Add stream=False and max_tool_calls after input=query,
# This regex finds input=query, and adds the two new parameters
content = re.sub(
    r'(input=query,\n)',
    r'\1    stream=False,\n    max_tool_calls=10,\n',
    content
)

# Replace all instructions with INSTRUCTIONS variable
# Match single-line instructions
content = re.sub(
    r'instructions="[^"]*",',
    'instructions=INSTRUCTIONS,',
    content
)

# Match multi-line instructions (with triple quotes)
content = re.sub(
    r'instructions="""[^"]*""",',
    'instructions=INSTRUCTIONS,',
    content,
    flags=re.DOTALL
)

# Write back
with open('techmart-rag-mcp-demo.ipynb', 'w') as f:
    f.write(content)

print("✅ Notebook fixed successfully!")
print("Changes applied:")
print("  - timeout: 60.0 → 120.0")
print("  - Added: stream=False")
print("  - Added: max_tool_calls=10")
print("  - All instructions → INSTRUCTIONS")

# Made with Bob

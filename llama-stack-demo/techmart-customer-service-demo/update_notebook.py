#!/usr/bin/env python3
"""Script to update notebook with universal instructions"""

import json

# Read the notebook
with open('techmart-rag-mcp-demo.ipynb', 'r') as f:
    notebook = json.load(f)

# Update all cells with response.create() calls
for cell in notebook['cells']:
    if cell['cell_type'] == 'code' and 'source' in cell:
        source = ''.join(cell['source'])
        
        # Check if this cell has a response.create() call
        if 'response = client.with_options' in source and 'responses.create' in source:
            lines = cell['source']
            new_lines = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                
                # Update timeout
                if 'timeout=60.0' in line:
                    line = line.replace('timeout=60.0', 'timeout=120.0')
                
                # Add stream=False and max_tool_calls after input=query
                if 'input=query,' in line or 'input=query,\n' in line:
                    new_lines.append(line)
                    # Add stream and max_tool_calls
                    indent = '    '
                    new_lines.append(f'{indent}stream=False,\n')
                    new_lines.append(f'{indent}max_tool_calls=10,\n')
                    i += 1
                    continue
                
                # Replace instructions with INSTRUCTIONS variable
                if 'instructions=' in line and 'INSTRUCTIONS' not in line:
                    # Skip multi-line instructions
                    if '"""' in line:
                        # Skip until we find the closing """
                        while i < len(lines) and not (lines[i].count('"""') == 2 or (i > 0 and '"""' in lines[i] and '"""' in lines[i-1])):
                            i += 1
                        # Replace with single line
                        indent = '    '
                        new_lines.append(f'{indent}instructions=INSTRUCTIONS,\n')
                        i += 1
                        continue
                    else:
                        # Single line instruction
                        indent = line[:len(line) - len(line.lstrip())]
                        new_lines.append(f'{indent}instructions=INSTRUCTIONS,\n')
                        i += 1
                        continue
                
                new_lines.append(line)
                i += 1
            
            cell['source'] = new_lines

# Write updated notebook
with open('techmart-rag-mcp-demo.ipynb', 'w') as f:
    json.dump(notebook, f, indent=1)

print("✅ Notebook updated successfully!")
print("All response.create() calls now use:")
print("  - timeout=120.0")
print("  - stream=False")
print("  - max_tool_calls=10")
print("  - instructions=INSTRUCTIONS")

# Made with Bob

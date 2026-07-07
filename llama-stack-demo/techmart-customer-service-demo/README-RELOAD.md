# Reloading Orders Data

The MCP server provides a `reload_orders` tool that allows you to refresh order data after manually updating the `orders.csv` file.

## How It Works

1. **Update the CSV file**: Modify `orders.csv` with new order data
2. **Call reload_orders tool**: The MCP server will reload the data from the file
3. **Data is refreshed**: All subsequent queries will use the updated data

## Methods to Update Orders

### Method 1: Volume Mount (Recommended for Development)

Mount your local `orders.csv` file into the container:

```bash
podman run -d \
  -p 9001:9001 \
  -v $(pwd)/data/orders.csv:/app/orders.csv:Z \
  --name mcp-orders \
  quay.io/vahirwad/mcp:techmart
```

After updating the local file, use the `reload_orders` tool through Llama Stack.

### Method 2: ConfigMap (Recommended for OpenShift)

Create a ConfigMap with your orders data:

```bash
oc create configmap orders-data --from-file=orders.csv=data/orders.csv
```

Mount it in your deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-orders-server
spec:
  template:
    spec:
      containers:
      - name: mcp-server
        image: quay.io/vahirwad/mcp:techmart
        volumeMounts:
        - name: orders-data
          mountPath: /app/orders.csv
          subPath: orders.csv
      volumes:
      - name: orders-data
        configMap:
          name: orders-data
```

Update the ConfigMap and restart the pod:

```bash
# Update ConfigMap
oc create configmap orders-data --from-file=orders.csv=data/orders.csv --dry-run=client -o yaml | oc apply -f -

# Restart pod to pick up changes
oc rollout restart deployment/mcp-orders-server
```

### Method 3: Copy File into Running Container

```bash
# Copy updated file into container
podman cp data/orders.csv mcp-orders:/app/orders.csv

# The reload_orders tool will pick up the changes
```

## Using the reload_orders Tool

### From Llama Stack Python Client

```python
from llama_stack_client import LlamaStackClient

client = LlamaStackClient(base_url="http://localhost:5001")

# Reload orders after updating the CSV file
response = client.agents.turn.create(
    agent_id="customer-service-agent",
    session_id="session-123",
    messages=[{
        "role": "user",
        "content": "Reload the orders data"
    }]
)

print(response.event.payload.turn.output_message.content)
```

### From Jupyter Notebook

```python
# After updating orders.csv, reload the data
response = agent_client.create_turn(
    agent_id=agent_id,
    session_id=session_id,
    messages=[{
        "role": "user", 
        "content": "Please reload the orders from the CSV file"
    }]
)

for chunk in response:
    if hasattr(chunk, 'event'):
        event = chunk.event
        if event.payload.event_type == 'turn_complete':
            print(event.payload.turn.output_message.content)
```

## CSV File Format

The `orders.csv` file must have these columns:

```csv
order_id,customer_email,product_name,category,order_date,delivery_date,price,status,is_opened
ORD-2024-001,customer@example.com,Product Name,Electronics,2024-04-10,2024-04-15,299.99,Delivered,no
```

**Required Fields:**
- `order_id`: Unique order identifier
- `customer_email`: Customer email address
- `product_name`: Name of the product
- `category`: Product category (affects return window)
- `order_date`: Order placement date (YYYY-MM-DD)
- `delivery_date`: Delivery date (YYYY-MM-DD)
- `price`: Order price (numeric)
- `status`: Order status (e.g., "Delivered", "Shipped")
- `is_opened`: Whether product was opened ("yes" or "no")

## Return Policy Rules

The MCP server uses these rules for return eligibility:

- **Electronics**: 15-day return window
  - Unopened: No restocking fee
  - Opened: 15% restocking fee
  
- **Other Categories**: 30-day return window
  - Unopened: No restocking fee
  - Opened: 10% restocking fee

## Demo Date

The server uses a static reference date of **April 21, 2024** for consistent demo behavior. When creating test data, use dates relative to this reference date.

## Troubleshooting

### Orders not updating after reload

1. Verify the CSV file was actually updated
2. Check file permissions (container must be able to read it)
3. Verify CSV format is correct
4. Check container logs: `podman logs mcp-orders`

### File not found errors

1. Ensure volume mount path is correct
2. Verify file exists at the mounted location
3. Check SELinux labels (use `:Z` flag in volume mount)

## Example Workflow

```bash
# 1. Start container with volume mount
podman run -d \
  -p 9001:9001 \
  -v $(pwd)/data/orders.csv:/app/orders.csv:Z \
  --name mcp-orders \
  quay.io/vahirwad/mcp:techmart

# 2. Edit orders.csv locally
vim data/orders.csv

# 3. Use reload_orders tool through Llama Stack
# (The tool will automatically reload the updated file)

# 4. Verify changes
# Query orders through the agent to confirm updates
```

## MCP Resource

The server also provides an MCP resource for getting order information:

```python
# Access the orders://info resource
resource = client.resources.get("orders://info")
print(resource.content)
```

This returns:
```json
{
  "orders_count": 10,
  "orders_file": "/app/orders.csv",
  "demo_date": "2024-04-21",
  "sample_orders": ["ORD-2024-001", "ORD-2024-002", ...]
}
# Running MCP Server Container with External Data

## Using External orders.csv

The MCP server supports loading `orders.csv` from outside the container using volume mounts.

### Option 1: Mount to Current Directory (Recommended)

```bash
podman run -p 9001:9001 \
  -v /path/to/your/orders.csv:/app/orders.csv:Z \
  quay.io/vahirwad/mcp:techmart
```

### Option 2: Mount Entire Data Directory

```bash
podman run -p 9001:9001 \
  -v /path/to/your/data:/app/data:Z \
  quay.io/vahirwad/mcp:techmart
```

### Option 3: Use Environment Variable (Requires Code Update)

First, update `orders_mcp_server.py` to support environment variable:

```python
# Add after line 16
ORDERS_PATH = os.getenv('ORDERS_CSV_PATH', 'orders.csv')
```

Then run:

```bash
podman run -p 9001:9001 \
  -e ORDERS_CSV_PATH=/data/orders.csv \
  -v /path/to/your/orders.csv:/data/orders.csv:Z \
  quay.io/vahirwad/mcp:techmart
```

## Example: Using Local Data

```bash
# From the project directory
cd llama-stack-demo/techmart-customer-service-demo

# Run with local orders.csv
podman run -p 9001:9001 \
  -v $(pwd)/data/orders.csv:/app/orders.csv:Z \
  quay.io/vahirwad/mcp:techmart
```

## Verify Data Loading

Check the container logs to confirm the CSV was loaded:

```bash
podman logs <container-id>
```

You should see:
```
🚀 Orders MCP Server starting...
📊 Loaded 10 orders from orders.csv
🌐 Server will run on http://0.0.0.0:9001
🔧 Available tools: get_order, check_return_eligibility
```

## OpenShift Deployment with ConfigMap

For OpenShift, use a ConfigMap to provide the CSV data:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orders-data
data:
  orders.csv: |
    order_id,customer_email,product_name,category,order_date,delivery_date,price,status,is_opened
    ORD-2024-001,customer1@example.com,Laptop Pro 15,Electronics,2024-04-01,2024-04-06,1299.99,Delivered,yes
    # ... more orders
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
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

## Dynamic Data Updates

To update data without rebuilding the container:

1. **Update the mounted file**: Changes are reflected immediately
2. **Restart the container**: `podman restart <container-id>`
3. **For OpenShift**: Update ConfigMap and rollout restart

```bash
# Update ConfigMap
oc create configmap orders-data --from-file=orders.csv --dry-run=client -o yaml | oc apply -f -

# Restart deployment
oc rollout restart deployment/mcp-server
```

## Notes

- The `:Z` flag in volume mounts is required for SELinux systems
- The server loads data at startup, so restart after CSV changes
- Ensure the CSV format matches the expected schema
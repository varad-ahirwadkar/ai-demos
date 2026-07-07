# Dynamic Data Upload for MCP Server

The MCP server now supports uploading CSV data dynamically via HTTP endpoints, eliminating the need for volume mounts or container restarts.

## New HTTP Endpoints

### 1. Upload Orders CSV

**Endpoint**: `POST /upload-orders`

Upload a new `orders.csv` file to update order data in real-time.

```bash
curl -X POST http://localhost:9001/upload-orders \
  -F "file=@/path/to/your/orders.csv"
```

**Response**:
```json
{
  "status": "success",
  "message": "Successfully uploaded and loaded 10 orders",
  "orders_count": 10
}
```

### 2. Get Orders Info

**Endpoint**: `GET /orders-info`

Get information about currently loaded orders.

```bash
curl http://localhost:9001/orders-info
```

**Response**:
```json
{
  "orders_count": 10,
  "orders_file": "orders.csv",
  "demo_date": "2024-04-21",
  "sample_orders": ["ORD-2024-001", "ORD-2024-002", "ORD-2024-003", "ORD-2024-004", "ORD-2024-005"]
}
```

## Usage Examples

### Example 1: Upload from Local File

```bash
# Upload your custom orders.csv
curl -X POST http://localhost:9001/upload-orders \
  -F "file=@data/orders.csv"
```

### Example 2: Upload from Script

```python
import requests

# Upload CSV file
with open('orders.csv', 'rb') as f:
    response = requests.post(
        'http://localhost:9001/upload-orders',
        files={'file': f}
    )
    print(response.json())
```

### Example 3: Upload from Web UI

```html
<!DOCTYPE html>
<html>
<body>
  <h2>Upload Orders CSV</h2>
  <form id="uploadForm">
    <input type="file" id="fileInput" accept=".csv" required>
    <button type="submit">Upload</button>
  </form>
  
  <div id="result"></div>

  <script>
    document.getElementById('uploadForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const formData = new FormData();
      formData.append('file', document.getElementById('fileInput').files[0]);
      
      const response = await fetch('http://localhost:9001/upload-orders', {
        method: 'POST',
        body: formData
      });
      
      const result = await response.json();
      document.getElementById('result').innerHTML = 
        `<p>${result.message}</p><p>Orders loaded: ${result.orders_count}</p>`;
    });
  </script>
</body>
</html>
```

## CSV Format Requirements

The uploaded CSV must contain these columns:

```csv
order_id,customer_email,product_name,category,order_date,delivery_date,price,status,is_opened
ORD-2024-001,customer1@example.com,Laptop Pro 15,Electronics,2024-04-01,2024-04-06,1299.99,Delivered,yes
ORD-2024-002,customer2@example.com,Wireless Mouse,Electronics,2024-04-07,2024-04-14,29.99,Delivered,no
```

**Required Fields**:
- `order_id`: Unique order identifier
- `customer_email`: Customer email address
- `product_name`: Product name
- `category`: Product category (e.g., Electronics, Home & Garden, Clothing)
- `order_date`: Order placement date (YYYY-MM-DD)
- `delivery_date`: Delivery date (YYYY-MM-DD)
- `price`: Product price (decimal)
- `status`: Order status (e.g., Delivered, Shipped, Processing)
- `is_opened`: Whether product was opened (yes/no)

## Benefits Over Volume Mounts

✅ **No Container Restart**: Data updates immediately without restarting
✅ **Remote Updates**: Upload from anywhere via HTTP
✅ **Web UI Integration**: Easy to build admin interfaces
✅ **API-Driven**: Integrate with CI/CD pipelines
✅ **Validation**: Server validates CSV format before loading
✅ **Logging**: All uploads are logged for audit trail

## OpenShift/Kubernetes Deployment

### Option 1: Using a Job to Upload Data

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: upload-orders-data
spec:
  template:
    spec:
      containers:
      - name: uploader
        image: curlimages/curl:latest
        command:
        - sh
        - -c
        - |
          curl -X POST http://mcp-server:9001/upload-orders \
            -F "file=@/data/orders.csv"
        volumeMounts:
        - name: orders-data
          mountPath: /data
      volumes:
      - name: orders-data
        configMap:
          name: orders-data
      restartPolicy: Never
```

### Option 2: Using Init Container

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  template:
    spec:
      initContainers:
      - name: upload-initial-data
        image: curlimages/curl:latest
        command:
        - sh
        - -c
        - |
          # Wait for MCP server to be ready
          until curl -f http://localhost:9001/orders-info; do
            echo "Waiting for MCP server..."
            sleep 2
          done
          
          # Upload data
          curl -X POST http://localhost:9001/upload-orders \
            -F "file=@/data/orders.csv"
        volumeMounts:
        - name: orders-data
          mountPath: /data
      containers:
      - name: mcp-server
        image: quay.io/vahirwad/mcp:techmart
        ports:
        - containerPort: 9001
      volumes:
      - name: orders-data
        configMap:
          name: orders-data
```

## Security Considerations

For production deployments:

1. **Add Authentication**: Protect upload endpoint with API keys or OAuth
2. **Rate Limiting**: Prevent abuse with rate limits
3. **File Size Limits**: Restrict maximum upload size
4. **Input Validation**: Validate CSV content thoroughly
5. **Audit Logging**: Log all upload attempts

Example with API key:

```python
from fastapi import Header, HTTPException

@app.post("/upload-orders")
async def upload_orders(
    file: UploadFile = File(...),
    api_key: str = Header(None, alias="X-API-Key")
):
    if api_key != os.getenv("UPLOAD_API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    # ... rest of upload logic
```

## Monitoring

Check upload status in container logs:

```bash
# Podman
podman logs -f <container-id>

# Kubernetes
kubectl logs -f deployment/mcp-server

# OpenShift
oc logs -f deployment/mcp-server
```

Expected log output:
```
✅ Orders updated: 10 orders loaded from uploaded file
```

## Troubleshooting

### Upload Fails with 400 Error

**Cause**: Invalid CSV format or missing required fields

**Solution**: Verify CSV has all required columns:
```bash
head -1 orders.csv
# Should show: order_id,customer_email,product_name,category,order_date,delivery_date,price,status,is_opened
```

### Upload Succeeds but Data Not Updated

**Cause**: File permissions or path issues

**Solution**: Check container logs for errors:
```bash
podman logs <container-id> | grep -i error
```

### Cannot Access Upload Endpoint

**Cause**: Port not exposed or firewall blocking

**Solution**: Verify port mapping:
```bash
podman ps
# Should show: 0.0.0.0:9001->9001/tcp
```

## Complete Example

```bash
# 1. Start the MCP server
podman run -d -p 9001:9001 --name mcp-server quay.io/vahirwad/mcp:techmart

# 2. Check current orders
curl http://localhost:9001/orders-info

# 3. Upload new orders
curl -X POST http://localhost:9001/upload-orders \
  -F "file=@new-orders.csv"

# 4. Verify update
curl http://localhost:9001/orders-info

# 5. Test MCP tools with new data
# (Use Llama Stack or MCP client to call get_order, check_return_eligibility)
```

Now you can update order data dynamically without any container restarts or volume mounts!
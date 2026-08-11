from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import logging
import sys
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("🚀 Kubernetes SRE MCP Server")
logger.info("=" * 60)
logger.info("Server Name: K8sSREServer")
logger.info("Namespace: llama-demo")
logger.info("Endpoint: http://localhost:9000/sse")
logger.info("")
logger.info("Available Tools:")
logger.info("  • list_pods() - List all pods in namespace")
logger.info("  • get_crashing_pods() - Find pods in error state")
logger.info("  • get_pod_logs(pod_name) - Get pod logs")
logger.info("=" * 60)
logger.info("Server is running... Press Ctrl+C to stop")
logger.info("")

mcp = FastMCP(
    "K8sSREServer",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
)

# Fixed namespace for this demo
NAMESPACE = "llama"

def get_k8s_client():
    """Get Kubernetes client"""
    try:
        from kubernetes import client, config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        return client
    except Exception as e:
        logger.error(f"K8s client error: {e}")
        return None

@mcp.tool()
def list_pods() -> dict[str, Any]:
    """
    List all pods in llama-demo namespace.
    
    Returns:
        Dictionary with all pods and their basic status
    """
    try:
        k8s = get_k8s_client()
        if not k8s:
            return {"error": "Kubernetes client not available"}
        
        v1 = k8s.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace=NAMESPACE)
        
        pod_list = []
        for pod in pods.items:
            pod_info = {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": "0/0",
                "restarts": 0,
                "age": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
            }
            
            # Calculate ready containers
            if pod.status.container_statuses:
                ready_count = sum(1 for c in pod.status.container_statuses if c.ready)
                total_count = len(pod.status.container_statuses)
                pod_info["ready"] = f"{ready_count}/{total_count}"
                pod_info["restarts"] = sum(c.restart_count for c in pod.status.container_statuses)
            
            pod_list.append(pod_info)
        
        logger.info(f"Listed {len(pod_list)} pods")
        return {
            "namespace": NAMESPACE,
            "pod_count": len(pod_list),
            "pods": pod_list
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}

@mcp.tool()
def get_crashing_pods() -> dict[str, Any]:
    """
    Get pods that are crashing or in error state in llama-demo namespace.
    
    Returns:
        Dictionary with crashing pods and their details
    """
    try:
        k8s = get_k8s_client()
        if not k8s:
            return {"error": "Kubernetes client not available"}
        
        v1 = k8s.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace=NAMESPACE)
        
        crashing_pods = []
        for pod in pods.items:
            restart_count = 0
            containers = []
            
            if pod.status.container_statuses:
                for container in pod.status.container_statuses:
                    restart_count += container.restart_count
                    state = "running"
                    reason = None
                    
                    if container.state.waiting:
                        state = "waiting"
                        reason = container.state.waiting.reason
                    elif container.state.terminated:
                        state = "terminated"
                        reason = container.state.terminated.reason
                    
                    containers.append({
                        "name": container.name,
                        "ready": container.ready,
                        "restart_count": container.restart_count,
                        "state": state,
                        "reason": reason
                    })
            
            # Include if pod has issues
            if pod.status.phase in ["Failed", "Unknown"] or restart_count > 0:
                crashing_pods.append({
                    "name": pod.metadata.name,
                    "phase": pod.status.phase,
                    "restart_count": restart_count,
                    "containers": containers
                })
        
        logger.info(f"Found {len(crashing_pods)} problematic pods")
        return {
            "namespace": NAMESPACE,
            "crashing_pods_count": len(crashing_pods),
            "pods": crashing_pods
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}

@mcp.tool()
def get_pod_logs(pod_name: str) -> dict[str, Any]:
    """
    Get logs from a specific pod in llama-demo namespace.
    
    Args:
        pod_name: Name of the pod
        
    Returns:
        Dictionary with pod logs (last 50 lines)
    """
    try:
        k8s = get_k8s_client()
        if not k8s:
            return {"error": "Kubernetes client not available"}
        
        v1 = k8s.CoreV1Api()
        
        # Get first container
        pod = v1.read_namespaced_pod(name=pod_name, namespace=NAMESPACE)
        container = pod.spec.containers[0].name if pod.spec.containers else None
        
        if not container:
            return {"error": "No containers found"}
        
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=NAMESPACE,
            container=container,
            tail_lines=50
        )
        
        logger.info(f"Retrieved logs from '{pod_name}'")
        return {
            "pod_name": pod_name,
            "namespace": NAMESPACE,
            "container": container,
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}

@mcp.resource("info://server")
def get_server_info() -> dict[str, Any]:
    """Get server information"""
    return {
        "name": "K8sSREServer",
        "version": "1.0.0",
        "description": "Simple K8s MCP server for llama-demo namespace",
        "namespace": NAMESPACE,
        "tools": ["list_pods", "get_crashing_pods", "get_pod_logs"],
        "transport": "sse",
        "endpoint": "http://localhost:9000/sse"
    }

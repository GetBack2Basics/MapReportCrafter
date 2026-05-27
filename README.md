# Map_Report_Crafter (Hybrid Cloud GIS)

A lightweight, Agentic GIS web application leveraging a Hybrid Cloud Architecture. It queries serverless Queensland State REST APIs for broad spatial data and uses a local Kubernetes PostGIS cluster for heavy-duty geoprocessing.

## Architecture Stack
* **Frontend:** Leaflet, Leaflet.Draw, html2pdf
* **Backend:** Flask, PostGIS, Kubernetes
* **Configuration:** Data-driven JSON sync via Python

## Setup Instructions

### 1. Synchronize Layers Config
Run the Python synchronization script to fetch serverless layer schemas and generate the configuration:
```bash
python3 sync_layers.py
```

### 2. Deploy Backend API to Kubernetes PostGIS Pod
Copy the API script directly to your active PostGIS Pod and start the Flask server inside it:
```bash
# 1. Identify the active PostGIS Pod name
export POD_NAME=$(kubectl get pods -n default -l app=postgis -o jsonpath='{.items[0].metadata.name}')

# 2. Copy the api.py script into the pod
kubectl cp backend/api.py default/$POD_NAME:/tmp/api.py

# 3. Start the Flask server in the background inside the Pod
kubectl exec -n default $POD_NAME -- bash -c "python3 /tmp/api.py </dev/null >/tmp/api.log 2>&1 &"
```

### 3. Serve Frontend
Serve the project root folder with any standard web server, such as Nginx or python's built-in HTTP module:
```bash
# Using Python
python3 -m http.server 8080
```

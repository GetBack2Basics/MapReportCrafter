# Map Report Crafter

Map Report Crafter is a lightweight, agentic GIS web application built to reduce the gap between raw spatial data and actionable environmental insight. It is designed for environmental consultants, urban planners, GIS administrators, and other users who need fast property-based spatial reporting.

The application uses a hybrid cloud architecture:

- **Serverless Queensland State REST APIs** for broad, real-time spatial data access
- **A local Kubernetes PostGIS cluster** for heavier geometric processing and locally hosted datasets

## Architecture Stack

- **Frontend:** Leaflet, Leaflet.Draw, html2pdf
- **Backend:** Flask, PostGIS, Kubernetes
- **Configuration:** Data-driven JSON synchronization via Python

## For End Users: Reporting Workflow

### Intelligent property search

Start typing a Queensland Lot/Plan number into the search bar. The application queries the live State Cadastre, auto-completes your entry, and flies the map directly to the selected parcel.

### Instant spatial intersections

As soon as a property is selected, the Universal Intersect Engine evaluates the parcel geometry across multiple data sources at once:

- **State REST APIs** for serverless, real-time checks against remote datasets such as vegetation management and strategic cropping land
- **Edge Kubernetes (PostGIS)** for more computationally intensive geometric analysis against locally hosted datasets such as bushfire prone areas and USLE soil K-factors

### Thematic visualization and metadata

Use the draggable Layer Manager to toggle layers on and off. Local PostGIS layers are rendered dynamically with attribute-driven thematic symbology so the map remains readable while still surfacing important classifications.

### One-click PDF export

Intersection results are presented in a clean table. Selecting the PDF export option generates a client-side report that captures the interactive map, highlighted property boundary, and configured reporting outputs in a single readable document.

## For Administrators: Config-First Architecture

You do not need to edit large amounts of frontend or backend code to add a new map layer. The application is driven by a single configuration source of truth.

### 1. Update `layers.json`

Open the master configuration file and define:

- the new layer
- its PostGIS table name
- the database column to query
- any categorical styling or reporting rules

### 2. Run the sync script

Execute:

```bash
python3 sync_layers.py
```

The backend validation process will query the Kubernetes database, verify that the configured tables and columns exist, and authorize the layer for use.

### 3. Refresh the frontend

The Leaflet frontend reads the JSON configuration dynamically. After refresh, the new layer, legend, thematic colors, and intersection reporting logic become available in the application.

## Setup Instructions

### 1. Synchronize the layer configuration

Run the Python synchronization script to fetch serverless layer schemas and generate the local configuration:

```bash
python3 sync_layers.py
```

### 2. Deploy the backend API to the Kubernetes PostGIS pod

Copy the API script into the active PostGIS pod, then start the Flask server inside the pod:

```bash
# 1. Identify the active PostGIS pod name
export POD_NAME=$(kubectl get pods -n default -l app=postgis -o jsonpath='{.items[0].metadata.name}')

# 2. Copy the api.py script into the pod
kubectl cp backend/api.py default/$POD_NAME:/tmp/api.py

# 3. Start the Flask server in the background inside the pod
kubectl exec -n default $POD_NAME -- bash -c "python3 /tmp/api.py </dev/null >/tmp/api.log 2>&1 &"
```

### 3. Serve the frontend

Serve the project root folder with any standard web server, such as Nginx or Python’s built-in HTTP server:

```bash
# Using Python
python3 -m http.server 8080
```

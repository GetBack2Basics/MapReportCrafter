# Map_Report_Crafter (Hybrid Cloud GIS)

Map_Report_Crafter is designed to eliminate the bottleneck between raw spatial data and actionable environmental insights. Whether you are an environmental consultant, an urban planner, or a GIS administrator, the system is built for speed and simplicity.

## Architecture Stack
* **Frontend:** Leaflet, Leaflet.Draw, html2pdf
* **Backend:** Flask, PostGIS, Kubernetes
* **Configuration:** Data-driven JSON sync via Python

##For the End-User (The Reporting Workflow)
#Intelligent Property Search:
Start typing a Queensland Lot/Plan number into the search bar. The system queries the live State Cadastre, auto-completes your entry, and instantly flies the map to the target parcel. (Alternatively, simply right-click anywhere on the map to auto-select the underlying property).

#Instant Spatial Intersections:
The moment a property is selected, the "Universal Intersect Engine" engages. The application takes the exact geometry of your parcel and simultaneously queries:

#State REST APIs: For serverless, real-time checks against remote datasets (e.g., Vegetation Management, Strategic Cropping Land).

#Edge Kubernetes (PostGIS): For heavy geometric math against locally hosted datasets (e.g., Bushfire Prone Areas, USLE Soil K-Factors).

#Thematic Visualization & Metadata:
Toggle layers on and off using the draggable Layer Manager. Local PostGIS layers are rendered dynamically using attribute-driven thematic symbology (e.g., "High Intensity" bushfire areas automatically render in dark red). Click the (i) icon next to any layer to view its live legend and access official state metadata URLs.

#One-Click PDF Export:
The intersection results populate a clean, readable table. Click the "📄 PDF" button to trigger a native, client-side render of the interactive map, the highlighted property boundary, and the constraint table into a shareable report.

##For the Administrator (The Config-First Architecture)
#No more digging through thousands of lines of JavaScript or Python to add a new map layer. The entire application is governed by a single Source of Truth.

#Update layers.json: Open the master configuration file and define your new layer, its PostGIS table name, and the specific database column you want to query. You can also define exact categorical symbology (Hex colors and friendly labels) right in the JSON.

#Run the Sync Script: Execute python3 sync_layers.py. The backend validation engine will automatically query the Kubernetes database, verify the tables and columns exist, and authorize the layer.

#Instant UI Refresh: The Leaflet frontend dynamically reads the JSON. Upon refresh, your new layer, its legend, its thematic colors, and its intersection report logic are immediately live in the application.

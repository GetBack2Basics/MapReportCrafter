# HERMES SYSTEM ARCHITECTURE & MEMORY RULES
*Context for FunGIS TrueView Project*

When operating on this project, Hermes MUST automatically adhere to the following rules to prevent environment crashes, map rendering failures, and terminal hangs:

1. KUBERNETES ANTI-HANG PROTOCOL: 
   Any background service started via `kubectl exec` MUST use the exact termination pattern: `</dev/null > /tmp/[logname].log 2>&1 & sleep 1`. Never start a background process without detaching standard input.

2. POSTGIS SRID SAFETY: 
   All spatial intersections (e.g., ST_Intersects) must account for coordinate system mismatches. Either cast both geometries to `ST_SetSRID(geom, 0)` to force a raw intersection, or dynamically detect the table's SRID and use `ST_Transform(GPS_Point, SRID)`.

3. DEFENSIVE API JSON: 
   All Flask routes must be wrapped in `try-except` blocks returning a `200 OK` status with `{"error": str(e)}`. Never allow Flask to return a raw 500 HTML error page, as it will crash the frontend JavaScript JSON parser.

4. QUEENSLAND WMS STANDARDS: 
   Leaflet WMS layers connecting to Queensland MapServers MUST use the public endpoint `gisservices.information.qld.gov.au` (NEVER use the internal `spatial-gis` endpoint). You must explicitly include wide group layers (e.g., `layers: '0,1,2,3,4'`) and set `maxZoom: 22` to ensure tiles render.

5. FRONTEND STARTUP BEHAVIOR (RANDOM LOT):
   When fetching a random lot plan on application load, the JavaScript must ONLY populate the search input field's value. It MUST NOT execute the search function or automatically zoom the map. The map should wait for the user to explicitly initiate the search.

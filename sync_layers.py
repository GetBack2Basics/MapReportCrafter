import json

data = {
    "mapLayers": [
        {
            "name": "Cadastre (State)",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/PlanningCadastre/LandParcelPropertyFramework/MapServer",
            "options": { "layers": [4], "opacity": 0.8, "transparent": True },
            "visibleByDefault": True
        },
        {
            "name": "Important Ag Areas (State)",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/Boundaries/AdminBoundariesFramework/MapServer",
            "options": { "layers": [86], "opacity": 0.6, "transparent": True },
            "visibleByDefault": False
        },
        {
            "name": "Vegetation Management (State)",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/Biota/VegetationManagement/MapServer",
            "options": { "layers": [109], "opacity": 0.6, "transparent": True },
            "visibleByDefault": False
        },
        {
            "name": "Land Systems (State)",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/GeoscientificInformation/SoilsAndLandResource/MapServer",
            "options": { "layers": [1302], "opacity": 0.6, "transparent": True },
            "visibleByDefault": False
        },
        {
            "name": "Strategic Cropping Land (State)",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/Boundaries/AdminBoundariesFramework/MapServer",
            "options": { "layers": [105], "opacity": 0.6, "transparent": True },
            "visibleByDefault": False
        }
    ],
    "localMapLayers": [
        {
            "name": "Universal Soil Loss Eq. (Local)",
            "table": "usle_data",
            "color": "#ff7800",
            "visibleByDefault": False
        }
    ],
    "restQueries": [
        {
            "label": "Important Ag Area",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/Boundaries/AdminBoundariesFramework/MapServer/86/query",
            "positiveText": "Yes",
            "negativeText": "No"
        },
        {
            "label": "Vegetation Management",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/Biota/VegetationManagement/MapServer/109/query",
            "positiveText": "Yes",
            "negativeText": "No"
        },
        {
            "label": "Land Systems",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/GeoscientificInformation/SoilsAndLandResource/MapServer/1302/query",
            "positiveText": "Yes",
            "negativeText": "No"
        },
        {
            "label": "Strategic Cropping Land",
            "url": "https://gisservices.information.qld.gov.au/arcgis/rest/services/Boundaries/AdminBoundariesFramework/MapServer/105/query",
            "positiveText": "Yes",
            "negativeText": "No"
        }
    ],
    "localQueries": [
        {
            "label": "USLE K-Factor (Local)",
            "endpoint": "/api/local_intersect",
            "payload": { "table": "usle_data", "column": "k_factor" },
            "fallbackText": "No Soil Data Intersected"
        }
    ]
}

with open("/home/ubuntu/fungis-app/layers.json", "w") as f:
    json.dump(data, f, indent=2)
print("layers.json successfully synchronized.")

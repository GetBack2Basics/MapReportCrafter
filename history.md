# Project History & Lessons Learned: Agentic GIS limits

## Background
A wet week project testing the limits of AI-orchestrated GIS development on a shoestring budget.

## Infrastructure
Deployed on Oracle Free Tier with $30 of Google API credits used for the AI agent (Hermes).

## AI Governance
Implemented a strict `budget.md` to throttle the orchestrator and prevent infinite looping/API burn.

## The Pivot
Originally scoped for QGIS, but pivoted to a web-native Leaflet architecture to better handle edge-compute integrations.

## Network Dramas
Documented intense struggles with Kubernetes Ingress controllers, external gateways, and CORS preflight (`OPTIONS`) failures when linking the frontend to the local PostGIS pods.

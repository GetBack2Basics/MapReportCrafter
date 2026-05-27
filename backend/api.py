from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2, json, random, re

app = Flask(__name__)
CORS(app)

def get_db(): return psycopg2.connect('dbname=fungis user=docker password=docker host=localhost')

@app.route('/api/search', methods=['GET'])
def search():
    try:
        q = request.args.get('q', '')
        conn = get_db(); cur = conn.cursor()
        cur.execute('SELECT lot_plan, ST_AsGeoJSON(ST_CurveToLine(shape)) FROM dcdb WHERE lot_plan ILIKE %s AND shape IS NOT NULL LIMIT 1', ('%' + q + '%',))
        result = cur.fetchone(); conn.close()
        return jsonify({'lot_plan': result[0], 'geometry': json.loads(result[1])}) if result else jsonify({'lot_plan': None, 'geometry': None})
    except Exception as e: return jsonify({'error': str(e)}), 200

@app.route('/api/report', methods=['GET'])
def get_report():
    try:
        q = request.args.get('q', '')
        conn = get_db(); cur = conn.cursor()
        cur.execute('SELECT zoning_name, noise_level FROM get_property_report(%s)', (q,))
        rows = cur.fetchall(); conn.close()
        return jsonify([{'zoning': r[0] or 'N/A', 'noise': r[1] or 'N/A'} for r in rows] if rows else [{'zoning': 'N/A', 'noise': 'N/A'}])
    except Exception as e: return jsonify({'error': str(e)}), 200

@app.route('/api/random', methods=['GET'])
def get_random():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT lot_plan FROM dcdb WHERE lot_plan IS NOT NULL AND lot_plan != '' AND shape IS NOT NULL ORDER BY ST_Area(shape) DESC LIMIT 100")
        rows = cur.fetchall(); conn.close()
        return jsonify({'lot_plan': random.choice(rows)[0] if rows else ''})
    except Exception as e: return jsonify({'error': str(e)}), 200

@app.route('/api/extent', methods=['GET'])
def get_extent():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT ST_YMin(ST_Extent(shape)), ST_XMin(ST_Extent(shape)), ST_YMax(ST_Extent(shape)), ST_XMax(ST_Extent(shape)) FROM dcdb")
        res = cur.fetchone(); conn.close()
        if res and res[0] is not None: return jsonify({'bounds': [[res[0], res[1]], [res[2], res[3]]] })
        return jsonify({'error': 'No data'})
    except Exception as e: return jsonify({'error': str(e)}), 200

@app.route('/api/identify', methods=['GET'])
def identify():
    try:
        lat = request.args.get('lat', type=float); lng = request.args.get('lng', type=float)
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COALESCE(ST_SRID(shape), 0) FROM dcdb WHERE shape IS NOT NULL LIMIT 1")
        srid = (cur.fetchone() or [0])[0]
        if srid == 0: cur.execute("SELECT lot_plan FROM dcdb WHERE ST_Intersects(shape, ST_SetSRID(ST_MakePoint(%s, %s), 0)) LIMIT 1", (lng, lat))
        else: cur.execute(f"SELECT lot_plan FROM dcdb WHERE ST_Intersects(shape, ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), {srid})) LIMIT 1", (lng, lat))
        res = cur.fetchone(); conn.close()
        return jsonify({'lot_plan': res[0] if res else "No overlap found", 'intersect_error': None})
    except Exception as e: return jsonify({'error': str(e)}), 200

@app.route('/api/local_intersect', methods=['POST', 'OPTIONS'])
def local_intersect():
    if request.method == 'OPTIONS': return jsonify({'status': 'ok'}), 200
    try:
        data = request.get_json(); geom = data.get('geometry'); table = data.get('table'); column = data.get('column')
        if not geom or not table or not column: return jsonify({'error': 'Missing payload'}), 200
        if not re.match(r'^[a-zA-Z0-9_]+$', table) or not re.match(r'^[a-zA-Z0-9_]+$', column): return jsonify({'error': 'Invalid schema'}), 200

        conn = get_db(); cur = conn.cursor()
        cur.execute(f"SELECT COALESCE(ST_SRID(geom), 0) FROM {table} WHERE geom IS NOT NULL LIMIT 1")
        srid = (cur.fetchone() or [0])[0]
        
        if srid == 0: query = f"SELECT {column} FROM {table} WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON(%s), 0)) LIMIT 1"
        else: query = f"SELECT {column} FROM {table} WHERE ST_Intersects(geom, ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), {srid})) LIMIT 1"
            
        cur.execute(query, (json.dumps(geom),))
        res = cur.fetchone(); conn.close()
        return jsonify({'result': res[0] if res else None})
    except Exception as e: return jsonify({'error': str(e)}), 200

# NEW ROUTE: Serve Local PostGIS data as GeoJSON to Leaflet map
@app.route('/api/local_layer', methods=['GET'])
def local_layer():
    try:
        table = request.args.get('table')
        bbox = request.args.get('bbox') # minLng,minLat,maxLng,maxLat
        if not table or not bbox or not re.match(r'^[a-zA-Z0-9_]+$', table): return jsonify({'error': 'Invalid params'}), 400
        
        coords = [float(x) for x in bbox.split(',')]
        conn = get_db(); cur = conn.cursor()
        
        cur.execute(f"SELECT COALESCE(ST_SRID(geom), 0) FROM {table} WHERE geom IS NOT NULL LIMIT 1")
        srid = (cur.fetchone() or [0])[0]
        
        envelope = f"ST_MakeEnvelope({coords[0]}, {coords[1]}, {coords[2]}, {coords[3]}, 4326)"
        if srid != 0: envelope = f"ST_Transform({envelope}, {srid})"
        
        # Pulls simplified geometries limited to the user's screen view to prevent browser crashes
        query = f"""
            SELECT jsonb_build_object('type', 'FeatureCollection', 'features', COALESCE(jsonb_agg(feature), '[]'::jsonb)) 
            FROM (
                SELECT jsonb_build_object(
                    'type', 'Feature', 
                    'geometry', ST_AsGeoJSON(ST_Transform(ST_Simplify(geom, 0.001), 4326))::jsonb, 
                    'properties', to_jsonb(t) - 'geom'
                ) AS feature 
                FROM (SELECT * FROM {table} WHERE ST_Intersects(geom, {envelope}) LIMIT 1000) t
            ) q;
        """
        cur.execute(query)
        res = cur.fetchone(); conn.close()
        return jsonify(res[0] if res[0] else {'type': 'FeatureCollection', 'features': []})
    except Exception as e: return jsonify({'error': str(e)}), 500

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000)

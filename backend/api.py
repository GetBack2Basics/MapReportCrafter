from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import subprocess
import json
import re

app = Flask(__name__)
CORS(app)
GEOM_META_CACHE = {}

def get_postgis_pod_name():
    cmd = "kubectl get pods -l app=postgis -o jsonpath='{.items[0].metadata.name}'"
    try:
        pod_name = subprocess.check_output(cmd, shell=True, text=True).strip()
        return pod_name if pod_name else "postgis-76b874bcf-2dz8t"
    except Exception:
        return "postgis-76b874bcf-2dz8t"


def is_safe_identifier(name):
    return isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None


def run_sql(query):
    safe_query = query.replace('"', '\\"')
    has_kubectl = subprocess.call(
        "command -v kubectl >/dev/null 2>&1",
        shell=True
    ) == 0

    if has_kubectl:
        pod_name = get_postgis_pod_name()
        cmd = f'kubectl exec -i {pod_name} -- psql -U docker -d fungis -tA -c "{safe_query}"'
    else:
        # When API runs inside the postgis pod, kubectl is usually unavailable.
        cmd = f'psql -U docker -d fungis -tA -c "{safe_query}"'

    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except Exception as e:
        print(f"SQL Error: {e}")
        return None


def sql_literal(text):
    return text.replace("'", "''")


def get_table_geom_meta(table):
    if table in GEOM_META_CACHE:
        return GEOM_META_CACHE[table]

    meta = run_sql(f"SELECT f_geometry_column, srid FROM geometry_columns WHERE f_table_name = '{table}' LIMIT 1;")
    if not meta:
        return None, None
    geom_col, srid = meta.split('|')
    if not is_safe_identifier(geom_col):
        return None, None
    srid_int = int(srid) if str(srid).isdigit() else 0
    GEOM_META_CACHE[table] = (geom_col, srid_int)
    return GEOM_META_CACHE[table]

@app.route('/api/local_layer', methods=['GET'])
def get_layer():
    try:
        table = request.args.get('table')
        bbox = request.args.get('bbox')
        if not table or not bbox:
            return jsonify({"error": "Missing params"}), 400
        if not is_safe_identifier(table):
            return jsonify({"error": "Invalid table name"}), 400

        geom_col, srid_int = get_table_geom_meta(table)
        if not geom_col:
            return jsonify({"type": "FeatureCollection", "features": [], "error": f"Geometry metadata not found for table '{table}'"})

        if srid_int > 0:
            intersect_geom_expr = f"ST_Transform(ST_MakeEnvelope({bbox}, 4326), {srid_int})"
            out_geom_expr = f"ST_AsGeoJSON(ST_Transform({geom_col}, 4326))::jsonb"
        else:
            # Fallback for malformed/unknown SRID metadata.
            intersect_geom_expr = f"ST_SetSRID(ST_MakeEnvelope({bbox}, 4326), 0)"
            out_geom_expr = f"ST_AsGeoJSON({geom_col})::jsonb"

        sql = f"""
        SELECT jsonb_build_object('type', 'FeatureCollection', 'features', COALESCE(jsonb_agg(feature), '[]'::jsonb))
        FROM (
            SELECT jsonb_build_object(
                'type', 'Feature',
                'geometry', {out_geom_expr},
                'properties', to_jsonb(t) - '{geom_col}'
            ) AS feature
            FROM (
                SELECT * FROM {table}
                WHERE ST_Intersects({geom_col}, {intersect_geom_expr})
                LIMIT 2000
            ) t
        ) row;
        """
        result = run_sql(sql)
        if not result:
            return jsonify({"type": "FeatureCollection", "features": [], "error": "No data returned from SQL"})

        parsed_json = json.loads(result)
        return jsonify(parsed_json)
    except Exception as e:
        return jsonify({"type": "FeatureCollection", "features": [], "error": str(e)})

@app.route('/api/local_intersect', methods=['POST'])
def local_intersect():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400

        table = data.get('table')
        column = data.get('column')
        geometry = data.get('geometry')
        if not table or not column or not geometry:
            return jsonify({"error": "Missing table, column, or geometry"}), 400
        if not is_safe_identifier(table) or not is_safe_identifier(column):
            return jsonify({"error": "Invalid table or column"}), 400

        geom_str = json.dumps(geometry)
        geom_col, srid_int = get_table_geom_meta(table)
        if not geom_col:
            return jsonify({"error": "Table geometry not found"}), 404

        parcel_geom = "ST_SetSRID(ST_GeomFromGeoJSON('{geom}'), 4326)".format(geom=geom_str)
        if srid_int > 0:
            parcel_geom = f"ST_Transform({parcel_geom}, {srid_int})"
        else:
            parcel_geom = f"ST_SetSRID({parcel_geom}, 0)"

        sql = f"SELECT \"{column}\" FROM {table} WHERE ST_Intersects({geom_col}, {parcel_geom}) LIMIT 1;"
        result = run_sql(sql)
        return jsonify({"result": result if result else None})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/local_multi_intersect', methods=['POST'])
def local_multi_intersect():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Missing JSON payload"}), 400

        geometry = data.get('geometry')
        queries = data.get('queries')
        if not geometry or not isinstance(queries, list) or len(queries) == 0:
            return jsonify({"error": "Missing geometry or queries"}), 400

        geom_str = json.dumps(geometry)
        results = []

        for q in queries:
            label = q.get('label')
            table = q.get('table')
            column = q.get('column')

            if not label or not table or not column:
                results.append({"label": label or "unknown", "error": "Missing label/table/column", "result": None})
                continue
            if not is_safe_identifier(table) or not is_safe_identifier(column):
                results.append({"label": label, "error": "Invalid table or column", "result": None})
                continue

            geom_col, srid_int = get_table_geom_meta(table)
            if not geom_col:
                results.append({"label": label, "error": "Table geometry not found", "result": None})
                continue

            parcel_geom = "ST_SetSRID(ST_GeomFromGeoJSON('{geom}'), 4326)".format(geom=geom_str)
            if srid_int > 0:
                parcel_geom = f"ST_Transform({parcel_geom}, {srid_int})"
            else:
                parcel_geom = f"ST_SetSRID({parcel_geom}, 0)"

            sql = f"SELECT \"{column}\" FROM {table} WHERE ST_Intersects({geom_col}, {parcel_geom}) LIMIT 1;"
            result = run_sql(sql)
            results.append({"label": label, "result": result if result else None})

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/build-meta', methods=['GET'])
def build_meta():
    try:
        cmd = ["git", "-C", "/home/ubuntu/fungis-app", "log", "-1", "--format=%cs|%ct|%h"]
        output = subprocess.check_output(cmd, text=True).strip()
        if output:
            date_text, unix_time, short_hash = output.split('|')
            hour_minute = subprocess.check_output(
                ["date", "-u", "-d", f"@{unix_time}", "+%H:%M"],
                text=True
            ).strip()
            return jsonify({
                "version": f"v{short_hash}",
                "dateText": date_text,
                "timeText": hour_minute,
            })
    except Exception:
        pass

    return jsonify({"version": "v1.0.0", "dateText": "2026-05-28", "timeText": "00:00"})


@app.route('/api/local_extent', methods=['GET'])
def local_extent():
    try:
        table = request.args.get('table')
        if not table:
            return jsonify({"error": "Missing table"}), 400
        if not is_safe_identifier(table):
            return jsonify({"error": "Invalid table name"}), 400

        geom_col, _ = get_table_geom_meta(table)
        if not geom_col:
            return jsonify({"error": "Table geometry not found"}), 404

        sql = f"""
        SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
        FROM (
            SELECT ST_Extent(ST_Transform({geom_col}, 4326)) AS e
            FROM {table}
        ) s;
        """
        result = run_sql(sql)
        if not result:
            return jsonify({"error": "No extent returned"}), 404

        minx, miny, maxx, maxy = result.split('|')
        return jsonify({
            "bbox": [float(minx), float(miny), float(maxx), float(maxy)]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/local_mvt/<table>/<int:z>/<int:x>/<int:y>.pbf', methods=['GET'])
def local_mvt(table, z, x, y):
    try:
        if not is_safe_identifier(table):
            return Response(status=400)

        geom_col, srid_int = get_table_geom_meta(table)
        if not geom_col:
            return Response(status=404)
        if srid_int <= 0:
            return Response(status=500)

        # Build an MVT where feature attributes are packed into a JSONB properties column.
        # This keeps payload small while still allowing style-by-attribute on the client.
        sql = f"""
        SELECT encode(
            COALESCE(ST_AsMVT(mvt_rows, 'layer0', 4096, 'geom'), '\\x'::bytea),
            'hex'
        )
        FROM (
            SELECT
                ST_AsMVTGeom(
                    ST_Transform({geom_col}, 3857),
                    ST_TileEnvelope({z}, {x}, {y}),
                    4096,
                    64,
                    true
                ) AS geom,
                (to_jsonb(t) - '{sql_literal(geom_col)}') AS properties
            FROM {table} t
            WHERE ST_Intersects(
                {geom_col},
                ST_Transform(ST_TileEnvelope({z}, {x}, {y}), {srid_int})
            )
            LIMIT 100000
        ) AS mvt_rows
        WHERE geom IS NOT NULL;
        """

        hex_blob = run_sql(sql)
        if hex_blob is None:
            return Response(status=500)

        hex_blob = hex_blob.strip()
        tile_data = bytes.fromhex(hex_blob) if hex_blob else b''
        return Response(tile_data, mimetype='application/vnd.mapbox-vector-tile')
    except Exception as e:
        print(f"MVT Error: {e}")
        return Response(status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
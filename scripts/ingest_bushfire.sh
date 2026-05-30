#!/bin/bash
set -euo pipefail

echo "Starting bushfire data ingestion..."

WORK_DIR="${TMPDIR:-/tmp}/bushfire"
mkdir -p "$WORK_DIR"
rm -rf "$WORK_DIR"/*

TABLE_NAME="${TABLE_NAME:-bushfire_data}"
SOURCE_SRID="${SOURCE_SRID:-947000}"
STRICT_STATEWIDE="${STRICT_STATEWIDE:-false}"
SOURCE_WKT='PROJCS["Albers_Conical_Equal_Area",GEOGCS["GCS_GDA_1994",DATUM["D_GDA_1994",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Albers"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["central_meridian",145.0],PARAMETER["standard_parallel_1",-12.0],PARAMETER["standard_parallel_2",-28.0],PARAMETER["latitude_of_origin",-28.0],UNIT["Meter",1.0]]'
SOURCE_PROJ4='+proj=aea +lat_1=-12 +lat_2=-28 +lat_0=-28 +lon_0=145 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'

POSTGIS_POD="${POSTGIS_POD:-}"
if [ -z "$POSTGIS_POD" ]; then
    POSTGIS_POD=$(kubectl get pods -l app=postgis -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
fi
if [ -z "$POSTGIS_POD" ]; then
    POSTGIS_POD=$(kubectl get pods -o name | sed -n 's|pod/||p' | grep '^postgis-' | head -n 1 || true)
fi
if [ -z "$POSTGIS_POD" ]; then
    echo "Error: Could not find a PostGIS pod. Set POSTGIS_POD env var and retry."
    exit 1
fi

# NOTE:
# These tokenized download links can be region-specific and expire.
# For reliable statewide loads, provide a full statewide list via BUSHFIRE_URLS_FILE.
URLS=(
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=NV6uiYGYmNgb2aL2jeFHEdTFYsWyFasU9rJC4x7zZhwtukvqCuJ3f%2FUHlX2Q0YZ%2FYCo3284QC%2BZfYb6Je6F9jj22BfWjI66T1csEF8z4EIjIe%2FYVErHAZrasDpx86AGCrJmxFM7ti%2FIbTjFLPPaclVl3vOKeaAWseQTTiZs47pcXIv6SvrbBHNLSvxAcKNPAT38E99%2B1QG8MIqPaNVvZLR4o7URopm3%2Blz%2Ff42iSsdj7IeYy8mFVbPk2RfbjGskiLx0n2q4%2FLWgjhPnDZaLJnhnesSHKwnL5v2kvmvl2nhaEtYXVOlR%2B1oc2hLME2NEgwbkeeI3As96TA5wJWFJzZakC8UWVaNV2oLQpMXc1BQf01du6VECMm%2BN0G6KuQbN2IxIc%2Bi6WflCaCkIAYnnfXbaE4K2m%2BWIkby5ZucvWIr92kYN1AouW1GX1ctRWNv7RguFk96zou4NjNe%2BnOrPISHMdAiPhhwCZ81g2wo6QHxS4dn7lqKFXXzR2QU3%2Bluz%2BwGbyzcDj2Ho4WfZSq4am%2FyNg9wrqj7RLreVVWVAlg%2BagLszyYg09Rqabo8OotXwuke7vaE6s6vWuwpxeKwFzlWggtUW1dzkmbP9lCRd0jb%2F2JeUhXZXrNoarcPGM%2FRG5A88WA6Sdwab6IIaTIdFW57sUpEub0ljwBgODlzIQQ8c%3D"
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=i8xkei6DCw99tSRnTgVOdC4NTPLAgM947NYuoJx37akyR76N9SJ6ABi%2BNSCJhWQwUSg10%2FhsO1GGmAYJe5IvI9KvXF32LpbxakQU523e%2F3lEFYUrfmtWOr%2BDPQdu0XvSE67hO5zPx5PZTQx%2BfGjrGOqBACKKAZMH2LiB5h2nWLQZZE3Np4gZjuKXDu8roN0Q7y743h2PYMPTIZYzbWtMgVAb6P8B5%2BTyMvP7KoCG1ywiZviJBzRnHx7eolEOnYF3nD90csk1vQbuTtIfNb2A9luOg0ahuVDABQY25VNwY3bDPDI4Jm7QbjPo3lACqtaRibqbapNalyvnbhS3kn%2BwqHcr4LRkMRR7Yrrm9oaZEt5NLbmkxdyFTTZuuE8uFuOZvFJ31ZZ77S%2FPFTfwvem3mK9N2xgbBlaD4gkJXvaqp7%2FkHeK9XWe3de4H278zCTEonK%2BtRApTt%2FvccpIC8kTnqBjMvb4Rj8IuvSoRFW%2BgQYXtPpCf9VhUOZ5Stcm%2FaONAy3eBViUCahjMyVCxKzb4ofnDEndflUydqQsUR15ezjOWKbZtNI8sHvK8QdrqN5iCgmYrDWmCFes8qjnpcVeOqlpSo3jNt9BDu3C2x6fMCpU5vLbD7iAnmx9V1GrdgYZoZCA44ttjMFUXEkofnWgvsA9T9Oy4uuQJRmUgCVHwHHU%3D"
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=L3NtKvUmAQreP9YIIqX0tO%2Bz6sgUHQhq8eW8sB3mXZoP0xspYiq9zObUnCwyQKRw3Uacep%2BiIOaFRXCd3XkrzNvxqo2wKSya8RZUjbv1XBSssZ7c%2FuX%2BkqzEtGBtHR%2F7PJ8afauI4r0i9UbBjJ42%2Bljtrjo04657VEnv89h42aFMx%2BKvngyOOEcL0VUI87Poq8iDQyiQK6i385aw6Mkax2VJ94MzSFUSvChk3zZ%2FLM4%2FFmHBX5rOqumzXV0TxuO13Eqimk%2FXh7LxET3fdny97DI9yZMwmbtccK%2FhQFOjO7mxEzGkThN0d9kHyz3EBVFwzEjFjuwLTCk02KDVbplX9FNSLmaE9N9YM%2F6nBefP69cHvc9GPmJfHb5CuO2XoU1wkP4g%2B72O4NUFgifWa2uqQJZRyymxwxqzBRCKJRiv7FfPT1llcPPFc7qUBU9%2FjKg727MJbAfXFQQM4RcOfXnJJBb4vB9WqzG2siMzVubf8UmY8bu7ZPh%2FrXAA3brcZj4c4v7sdeNRCAuvA0AF8GhxGxMkMv6DOokND1oikLXzJ3F%2BsHpZtolqKfXlHU6u1wCFHT1sq7ecEO1StW2h5IPurIFdlxu7bpOvcQYJz8jZZWwiKSLDuJlGGbCd5x8BIV%2Brnq6AN39Ssw2IKmM1%2BJbS5DoiSpzMvat9g1kM24OR%2Fa0%3D"
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=ePSgRbDSdgFCmOM5J1gfKZ1SiSdjA0OmxtGUuT%2Fpvq2Nsj14%2Bf0X%2F4LHE%2B6UziGufxPaOwoaLZc0gCwdBRB2jTDdUNK1FWyxhzJXAMZh%2Byw8Qx4MTjT5OeTTxLC3uaGwbnFa6PzdA%2F4xPrFFim1jzOqODR7zNVvDDXRL%2B%2B9%2F6z%2BtXf8wYt7cK44CTPlt3O3lnzsjbWj%2BFpZONMXpwHKCsCVo%2Fv%2FheXwDGvX6hCwzCcl9h6wWWXCW5HemVwdomLaR7OqyymxxaQFyrg7%2BREY%2B8dngLVsDEj88rISbn1taqRYJUl%2FgR4Nv3%2FzXBY202CKJFXIP327ajvlRgsE1iOH2NFGWEsqNzmsS%2Bi%2F%2FrPqKIxEAbkI4igyEaFUbujqSMQzmiRUSpWuMdNCoEhJzU95XpzaId2CVkM2Na00MybwBBkTVg06B%2F6zNC76x322MipVwaFlSlG8yiYtTdutALos1wkv2Luhccn7DMsC91gJ4p2azRPZjLKSCNASJUo%2Ff5KEXT%2B9PUGJ9O3GYxlgPvitSKeT0jAJOG2OO4eM6N6bZ6%2BKnHXRM0rNGwdViaYfyBWm1blYhB8CUSjVsaZbGR%2F6vrbJ43TvhoJTrD0stvnNwQq7pkhGx05wc9h49X1HAXPa%2Blt%2Bq1Dwyb9lih8%2FylXr47jbVRsCH9W%2BADD%2FfTMp1JZo%3D"
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=Lj%2BQdlWLj6xsLlKCaP3VllqIag4u1MOwbrNoKHN5GgPXFfHRHiQj7pbLE30i6mDpi5DoyCpjt7ZD%2Fl990ttkxGBieKjHYi3fz6%2B9JSJitZ76NbQYVlP33AetywTMoShDuJeZsYBSXtX4xbRt1UucD04NGTJpiZCbs%2Fi%2Ba4ilY5AcExqjLg7py1umxymudt502fnv0aCHQIEGJHr1%2F2RE57pWFwIDrV2COga9IzQvBSF4xsGYLYCKLLNyJ54TWDbO5V0rGWeZMUqOv8ULYKT1cgeD9XRFA8exsVQeOxgKTuWp%2BPpYmKsCF6bbllAFMNye%2FzBiA49c5Syp7g7XI2wUNB6j9JbW%2F2okC63GFRPCmjFYrlPH38MT%2FzoOudHUkBnjW7ECvNuukuJXO6kMOKEjeOc0Xzev6BkwbNwlgwZS95fJhZjpvw%2BEBAlUSIPqD%2BOx%2FgIdIy3cGXWAzltcmSTsKNrp2LNARdoCm1OHwxPhREO9RoaMBr5NzAg6oUYrOKm0hwnbl11FxGoj8mB0nJ2Xgx%2B%2Bw3FxhGs5SnEesnZ%2FGhRkoy9ctM654ShVIQOvs2IsswbV6YFAUDvTmQ6fNfzHEjvyMrX8ap30Z4IZXk253%2BM7ebEgHZ%2BMu5%2BMZx5wAq9MRFrWXMVMzROAip3VQfpIzh2ej08D%2FKQXrGhsGld9ZKw%3D"
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=Y22zmh9jOo7ZcblEbDg64r6QzhwHnKgIma3ziT0ZNAQYkWUzXxTVgcwmsODSuf1qMvLjRx%2FWaYXlqOeSb1DCVBAg0lT6bmrTZr%2BodyKkzdhx1ujVJ90S22e4QZ%2ByrOuKh2sWTORBxfONnphavVm2MxOOULy7A47ZkA4iKeU9zt0QA7iF2ophMhZ9suxqpt71iwE8fJkSCdvTYPD4WDDCbU%2B9mf1l%2FfTUg5ZHr3kYpqaiVSzPn1uiHUbsLcRv5eLEcoaccT4L29vjd5wLOcL5GW5WRoFGagTAuGBRvqiqY6G%2FAM1zd4RM93YjZZLxHdMON5TuuPKOVqq8co4rT3fpRRAoLh0om4CbftL%2FP1m6SAYnu2aneWBZbhOfrLbGaSHuGR4uLHkXSABn0Fmu%2FJH5wvoMZx4EgRACg7WLTLuX6imSD7pq3pcw2SrVlxOjeGUYHEryFwqNiweO2ll9QZiXa1VFUcFw%2BQ8RIImgB8BeXvqCPEHYrjoNE%2FSiG5p7SJlizr%2BBxtv0RWUm3c1aRoNyrrLAcdMWnC%2Bhl5x%2Fly4uc8YXMAwVkrGgd8WEihGrgAphu2%2F6KHqSxPdcjAJWSL4Ai6Ss413u9t0ZxwBVbWRW%2B0JUDpNr9Bt6cCYTjS5sLvNzd6uTEpqmOrbYbceEkiZSk9Aw59FJNe2RAM2cxie%2BXPw%3D"
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=U4s%2F3fsNTxck9w4VkllZLMZ0OE70uwx9AmjyMSlsSo0UGW7y4x8TkP%2B4mz%2FNSbcsP8GhGsIL4yAdd4quv%2F06af47NsYbZprdcQhf9Gz6gzmOBjVWQJajIzNnjtjhQyhfzt%2B%2FZ%2F4uPs%2BRvBlYsVMyX%2BisYk%2BJk5fWZp3%2B1cd4e%2FgrZeoqm0HcrCDtRsluLeYEl9gHnT%2Bnm%2BxebpMZH%2FDJqktDDZMBEpmkWBN8g5Z6JL3B3oa77GPB9OcfzCDUTGCqS4z32RahfWom7zOUx62f8qiPp%2FtU06Q8Xs%2BeLgHZiJYuVwG1wesh3aLjZvq6YkYdcQ0ztdhjnLs7vuOGaYOpQ5Pz6L6xijLfxir61RX6kUq2OSxKBQR4lgM%2BAj8Kden9tvzS2so%2B7x14tWqko51l1TYAl%2BI%2B1%2B%2BsZFMI5eYvyPsjCGCE%2FE%2BPGB%2FDio3EPog4k58nHTDyA707HExuChV8VhSCulxzHPDKo2cxHf6DlfdVJ%2BPOWDpcxz7MH5njAmyE1daHPuvyM4tvBAnsoEvWgw3dgQbfOlMcozF9PTd7iNojiPfZ9Zagzg6PUQDmvOnDVeg1lDUUCTes8bWfc6YSwlEpXDBYQ8wfPhhknamJDH2XieTmpqls8JdzUSFTNz8TXfxgJhMF2IDVRtK34ReEmlQ%2FSMLriP1HJgum7GOnrVA%3D"
"https://qldspatial.information.qld.gov.au/DownloadService/Download.aspx?token=bO3zKqJzG4RVjTTeRyn%2F%2BPwLObYvsJxvTJp5Dah3LsbDab5vm7b%2F1c58%2BqWhXDZIqIdcp48sJ90KRlYlkvOqPeK3ZMb04AOgwHQ9%2BhuOHMdfdFXuwCu%2BXvFB1BTWpSqxABc0OBu0dqLv5EqC5mO2WUeCkEq1EDhjtt3X%2BhmJvAW1a533Q0Wh1k6BtHXQ%2FCM0PFIYJSuLWj4RZyQu0JIrIj8MxNCVuba0rK8jIh6JNPmADhsmzzkOndCGLf8ih7%2BxDcRAtO7DBwwlzCgpvI5qYTDHKM3EhuGJhw8HFvNUZi00TMm2AcFqqgwpWSsqbGLAoGQOURbFS5EQ26eoZ8LRDnfJS2igwZ99uYGrDUq%2Frk2dstm28e8tna9TWLdP5vlrQD1RweXPYYwfzMrMT1qtjNrrL%2FIBuQ0DyYGVF1qKJHkef%2BziaEF5r6XdxATC2GSRW4lZmVgmkVXmFUCEYf2MndPjXxQNiqJaa%2FvDkaHLbDKVeg1I2c67Ji47bp0oCq1XJ3wHvOFIc3Miqh1XiaXrAeDA0SGL%2FlJqh%2FD0%2Fz0VVmOkyBkPCSI86jxCfiGkchKaoWzHHTFMMIA1zZcpxNRdcfEXU1SW9Vh1%2F1OA1FnspatX6X0UcBtl5X3vf%2FtfvLFGVIJCKnlIG99x1C0E2U%2BDd58Gajz%2BdfLAid6GfbeeO4o%3D"
)

if [ -n "${BUSHFIRE_URLS_FILE:-}" ]; then
    if [ ! -f "$BUSHFIRE_URLS_FILE" ]; then
        echo "Error: BUSHFIRE_URLS_FILE not found: $BUSHFIRE_URLS_FILE"
        exit 1
    fi
    mapfile -t URLS < <(grep -v '^\s*#' "$BUSHFIRE_URLS_FILE" | sed '/^\s*$/d')
fi

if [ "${#URLS[@]}" -eq 0 ]; then
    echo "Error: No bushfire dataset URLs provided."
    exit 1
fi

sql_exec() {
    kubectl exec -i "$POSTGIS_POD" -- psql -v ON_ERROR_STOP=1 -U docker -d fungis "$@"
}

ensure_source_srid() {
    cat <<SQL | sql_exec
INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text)
VALUES ($SOURCE_SRID, 'QSPATIAL', $SOURCE_SRID, '$SOURCE_WKT', '$SOURCE_PROJ4')
ON CONFLICT (srid) DO UPDATE
SET auth_name = EXCLUDED.auth_name,
    auth_srid = EXCLUDED.auth_srid,
    srtext = EXCLUDED.srtext,
    proj4text = EXCLUDED.proj4text;
SQL
}

ensure_source_srid

dataset_index=0
imported_shp_count=0

for url in "${URLS[@]}"; do
    echo "----------------------------------------"
    echo "Processing dataset $dataset_index/${#URLS[@]}..."

    ZIP_PATH="$WORK_DIR/bpa_${dataset_index}.zip"
    EXTRACT_DIR="$WORK_DIR/extracted_${dataset_index}"

    echo "Downloading zip..."
    wget -q "$url" -O "$ZIP_PATH"

    echo "Extracting zip..."
    mkdir -p "$EXTRACT_DIR"
    unzip -q -o "$ZIP_PATH" -d "$EXTRACT_DIR"

    mapfile -t SHP_FILES < <(find "$EXTRACT_DIR" -type f \( -name "*.shp" -o -name "*.SHP" \) | sort)
    if [ "${#SHP_FILES[@]}" -eq 0 ]; then
        echo "Error: No shapefile found in dataset $dataset_index"
        exit 1
    fi

    echo "Found ${#SHP_FILES[@]} shapefile(s) in dataset $dataset_index"

    for shp_file in "${SHP_FILES[@]}"; do
        if [ "$imported_shp_count" -eq 0 ]; then
            mode="-d"
        else
            mode="-a"
        fi

        echo "Ingesting $shp_file with mode $mode"
        shp2pgsql "$mode" -s "$SOURCE_SRID" -W "LATIN1" "$shp_file" "$TABLE_NAME" \
            | sql_exec > "$WORK_DIR/ingest_${dataset_index}_${imported_shp_count}.log" 2>&1

        imported_shp_count=$((imported_shp_count + 1))
    done

    rm -rf "$ZIP_PATH" "$EXTRACT_DIR"
    echo "Dataset $dataset_index ingested successfully"

    dataset_index=$((dataset_index + 1))
done

echo "----------------------------------------"
echo "Imported $imported_shp_count shapefile(s)"

echo "Verifying row counts..."
sql_exec -c "SELECT COUNT(*) AS rows, COUNT(DISTINCT class) AS class_count FROM $TABLE_NAME;"

echo "Verifying extent in EPSG:4326..."
coverage_output=$(sql_exec -At -c "
WITH e AS (
  SELECT ST_Extent(ST_Transform(geom, 4326)) AS ext
  FROM $TABLE_NAME
)
SELECT
  round(ST_XMin(ext)::numeric, 6) || ',' ||
  round(ST_YMin(ext)::numeric, 6) || ',' ||
  round(ST_XMax(ext)::numeric, 6) || ',' ||
  round(ST_YMax(ext)::numeric, 6) || ',' ||
  CASE
    WHEN ST_XMin(ext) <= 138.0
      AND ST_XMax(ext) >= 153.0
      AND ST_YMin(ext) <= -28.0
      AND ST_YMax(ext) >= -11.0
    THEN 'statewide'
    ELSE 'partial'
  END
FROM e;")

IFS=',' read -r min_lon min_lat max_lon max_lat coverage_flag <<< "$coverage_output"
echo "Loaded extent: min_lon=$min_lon min_lat=$min_lat max_lon=$max_lon max_lat=$max_lat"

if [ "$coverage_flag" != "statewide" ]; then
    if [ "$STRICT_STATEWIDE" = "true" ]; then
        echo "ERROR: Loaded extent is partial, not statewide Queensland."
        echo "Check your URL list in BUSHFIRE_URLS_FILE and ensure it includes all QLD regional packs."
        exit 2
    fi

    echo "WARNING: Loaded extent is partial, not statewide Queensland."
    echo "Proceeding because STRICT_STATEWIDE is set to false."
fi

echo "Bushfire ingestion complete with statewide coverage."

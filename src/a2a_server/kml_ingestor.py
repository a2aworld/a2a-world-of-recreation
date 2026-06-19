import asyncio
import asyncpg
import os
import xml.etree.ElementTree as ET

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://a2a:a2a_dev_password@localhost:5432/a2a_world")
KML_PATH = r"d:\E.A.R.T.H\EARTH-A2A-Swarm\legacy_archive\knowledge_base\Master.kml"

async def ingest_kml_to_db():
    current_path = KML_PATH
    print(f"Parsing KML from {current_path}...")
    if not os.path.exists(current_path):
        # Fallback
        fallback_path = r"d:\E.A.R.T.H\EARTH-A2A-Swarm\observatory\public\artwork.kml"
        if os.path.exists(fallback_path):
            current_path = fallback_path
        else:
            print("KML file not found!")
            return

    namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
    tree = ET.parse(current_path)
    root = tree.getroot()

    placemarks = root.findall('.//kml:Placemark', namespaces)
    excluded_names = ['polygon', 'path', 'untitled', 'point', 'linestring', 'linearring', 'the', 'a', 'an']
    
    entities = {}

    for pm in placemarks:
        name_node = pm.find('kml:name', namespaces)
        if name_node is None or name_node.text is None:
            continue
        
        full_name = name_node.text.strip()
        subject_name = full_name.split('-')[0].strip()
        
        if not subject_name or subject_name.lower() in excluded_names or len(subject_name) < 3:
            continue

        if subject_name not in entities:
            entities[subject_name] = {
                "bounding_box": {"min_lat": 90, "max_lat": -90, "min_lon": 180, "max_lon": -180},
            }
        
        coords_node = pm.find('.//kml:coordinates', namespaces)
        if coords_node is not None and coords_node.text:
            coords_text = coords_node.text.strip()
            coord_pairs = coords_text.split()
            
            lats, lons = [], []
            for pair in coord_pairs:
                parts = pair.split(',')
                if len(parts) >= 2:
                    try:
                        lon, lat = float(parts[0]), float(parts[1])
                        lons.append(lon)
                        lats.append(lat)
                    except ValueError:
                        continue
            
            if lats and lons:
                eb = entities[subject_name]["bounding_box"]
                eb["min_lat"] = min(eb["min_lat"], min(lats))
                eb["max_lat"] = max(eb["max_lat"], max(lats))
                eb["min_lon"] = min(eb["min_lon"], min(lons))
                eb["max_lon"] = max(eb["max_lon"], max(lons))

    # Calculate centroids
    final_entities = []
    for name, data in entities.items():
        eb = data["bounding_box"]
        if eb["min_lat"] == 90:
            continue
        lat = (eb["min_lat"] + eb["max_lat"]) / 2
        lon = (eb["min_lon"] + eb["max_lon"]) / 2
        final_entities.append((name, round(lat, 6), round(lon, 6)))

    print(f"Extracted {len(final_entities)} distinct entities. Connecting to DB...")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Clearing old random puzzle pieces...")
        await conn.execute("DELETE FROM puzzle_pieces")

        print("Inserting True KML Puzzle Pieces...")
        for name, lat, lon in final_entities:
            framework = "emerald_decoder"
            encrypted = f"ENCRYPTED_{framework.upper()}_{name.replace(' ', '_')}"
            
            await conn.execute(
                """
                INSERT INTO puzzle_pieces (latitude, longitude, required_framework, encrypted_payload, decrypted_text)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (latitude, longitude) DO NOTHING
                """,
                lat, lon, framework, encrypted, name
            )
            
        print("Successfully seeded True Puzzle Pieces from KML.")
    except Exception as e:
        print(f"Error seeding true puzzle pieces: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(ingest_kml_to_db())

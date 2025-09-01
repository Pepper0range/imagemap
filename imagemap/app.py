from flask import Flask, render_template, jsonify, request
import os
from datetime import datetime
import piexif
from werkzeug.utils import secure_filename
import math
import json

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join("static", "bilder")
DATA_FILE = "bilderdaten.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_gps_data(img_path):
    try:
        exif_dict = piexif.load(img_path)
        gps = exif_dict.get("GPS")

        if gps:
            def dms_to_deg(value):
                d = value[0][0] / value[0][1]
                m = value[1][0] / value[1][1]
                s = value[2][0] / value[2][1]
                return d + (m / 60) + (s / 3600)

            lat = dms_to_deg(gps[2])
            if gps[1] == b'S':
                lat = -lat

            lon = dms_to_deg(gps[4])
            if gps[3] == b'W':
                lon = -lon

            return lat, lon
    except Exception as e:
        print(f"Kein GPS in {img_path}: {e}")
    return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  #Erdradius in Metern
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def group_images(bilder, max_distance=2):
    groups = []
    for bild in bilder:
        placed = False
        for group in groups:
            for member in group:
                if haversine(bild['lat'], bild['lon'], member['lat'], member['lon']) <= max_distance:
                    group.append(bild)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            groups.append([bild])
    return groups

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    try:
        with open(DATA_FILE, "r") as f:
            bilder = json.load(f)
    except:
        bilder = []
    gruppen = group_images(bilder)
    return jsonify(gruppen)

@app.route("/upload", methods=["POST"])
def upload():
    bild = request.files.get("bild")
    name = request.form.get("name")
    tag = request.form.get("tag")
    info = request.form.get("info")
    adv = request.form.get("adv") == "true" or request.form.get("adv") == "on"
    lat = request.form.get("lat")
    lon = request.form.get("lon")

    if not bild:
        return jsonify({"error": "Kein Bild erhalten"}), 400

    filename = secure_filename(bild.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    bild.save(save_path)

    if not adv:
        lat_read, lon_read = get_gps_data(save_path)
        if lat_read is not None:
            lat = lat_read
        if lon_read is not None:
            lon = lon_read

    try:
        lat = float(lat)
        lon = float(lon)
    except:
        return jsonify({"error": "Ungültige Koordinaten"}), 400

    eintrag = {
        "bildpfad": f"bilder/{filename}",
        "name": name,
        "tag": tag,
        "info": info,
        "lat": lat,
        "lon": lon,
        "datum": datetime.now().isoformat()
    }

    try:
        with open(DATA_FILE, "r") as f:
            daten = json.load(f)
    except:
        daten = []

    daten.append(eintrag)
    with open(DATA_FILE, "w") as f:
        json.dump(daten, f, indent=2)

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import io
import csv

# Optional DB import with safe fallback
try:
    from database import db
    DB_AVAILABLE = db is not None
except Exception:
    DB_AVAILABLE = False

app = FastAPI(title="Panchayat Agricultural Dashboard API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage as simple demo (no DB)
DATA: List[Dict[str, Any]] = []

class RecommendationRequest(BaseModel):
    village: Optional[str]
    temperature: Optional[float]
    rainfall: Optional[float]
    soil: Optional[str]

@app.get("/")
def root():
    return {"ok": True, "message": "API running"}

@app.get("/test")
async def test():
    # Simple readiness + DB status if available
    status = {
        "backend": "ok",
        "database": "available" if DB_AVAILABLE else "unavailable",
    }
    if DB_AVAILABLE:
        try:
            # Attempt a lightweight call to list collection names
            names = db.list_collection_names()
            status.update({
                "connection_status": "connected",
                "collections": names[:10]
            })
        except Exception as e:
            status.update({
                "connection_status": f"error: {type(e).__name__}",
            })
    return status

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

    decoded = content.decode('utf-8', errors='ignore')
    reader = csv.DictReader(io.StringIO(decoded))
    rows = []
    for row in reader:
        # Normalize keys
        normalized = {k.strip().lower(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
        rows.append(normalized)
    global DATA
    DATA = rows
    # Summary
    columns = list(reader.fieldnames) if reader.fieldnames else []
    summary = {
        "rows": len(rows),
        "columns": [c.lower() for c in columns],
    }
    return {"summary": summary}

@app.get("/data")
async def get_data(village: Optional[str] = None, crop: Optional[str] = None, season: Optional[str] = None):
    def match(row):
        def eq(a,b):
            return (a or '').strip().lower() == (b or '').strip().lower()
        if village and not eq(row.get('village'), village):
            return False
        if crop and not eq(row.get('crop'), crop):
            return False
        if season and not eq(row.get('season'), season):
            return False
        return True
    filtered = [r for r in DATA if match(r)]
    return {"count": len(filtered), "data": filtered[:1000]}

@app.post("/recommend")
async def recommend(req: RecommendationRequest):
    # Simple rule-based recommendations
    soil = (req.soil or '').lower()
    rainfall = req.rainfall or 0
    temp = req.temperature or 0
    options = []
    if soil in ["loam", "clay loam", "sandy loam"] and 600 <= rainfall <= 1200 and 20 <= temp <= 30:
        options.append({"crop": "Rice", "reasons": ["Needs moderate to high rainfall", "Grows well in loamy soils"], "inputs": {"fertilizer": "NPK 100:50:50", "water": "High"}})
    if 400 <= rainfall <= 800 and 18 <= temp <= 28:
        options.append({"crop": "Wheat", "reasons": ["Moderate rainfall", "Cooler temperatures"], "inputs": {"fertilizer": "NPK 120:60:40", "water": "Medium"}})
    if soil in ["sandy", "sandy loam"] and 200 <= rainfall <= 500 and 22 <= temp <= 35:
        options.append({"crop": "Millets", "reasons": ["Tolerant to low rainfall", "Thrives in sandy soils"], "inputs": {"fertilizer": "NPK 40:20:20", "water": "Low"}})
    if rainfall >= 1000 and temp >= 25:
        options.append({"crop": "Sugarcane", "reasons": ["High water requirement", "Warm climate"], "inputs": {"fertilizer": "NPK 150:60:60", "water": "Very High"}})
    if not options:
        options.append({"crop": "Pulses", "reasons": ["Adaptable to various soils", "Low to moderate water"], "inputs": {"fertilizer": "DAP basal + Topdress Urea", "water": "Low-Medium"}})
    return {"village": req.village, "recommendations": options[:5]}

@app.get("/metrics")
async def metrics():
    # compute basic metrics
    if not DATA:
        return {"total": 0, "unique_crops": 0, "avg_temp": 0, "avg_rain": 0, "total_area": 0}
    total = len(DATA)
    crops = set()
    temp_sum = 0.0
    rain_sum = 0.0
    area_sum = 0.0
    for r in DATA:
        c = r.get('crop')
        if c:
            crops.add(c.strip().lower())
        try:
            temp_sum += float(r.get('temperature', 0) or 0)
        except Exception:
            pass
        try:
            rain_sum += float(r.get('rainfall', 0) or 0)
        except Exception:
            pass
        try:
            area_sum += float(r.get('area', 0) or 0)
        except Exception:
            pass
    avg_temp = temp_sum/total if total else 0
    avg_rain = rain_sum/total if total else 0
    return {"total": total, "unique_crops": len(crops), "avg_temp": round(avg_temp,2), "avg_rain": round(avg_rain,2), "total_area": round(area_sum,2)}

@app.get("/top-crops")
async def top_crops():
    from collections import Counter
    counter = Counter()
    for r in DATA:
        c = (r.get('crop') or '').strip().lower()
        if c:
            counter[c]+=1
    return counter.most_common(5)

# Groundwater monitoring endpoints (demo)
class GroundwaterEvent(BaseModel):
    village: str
    usage_liters: float
    leak_detected: bool = False

GROUNDWATER: List[GroundwaterEvent] = []

@app.post("/groundwater")
async def log_groundwater(event: GroundwaterEvent):
    GROUNDWATER.append(event)
    alert = None
    if event.usage_liters > 10000:
        alert = f"High groundwater usage in {event.village}"
    if event.leak_detected:
        alert = (alert + "; ") if alert else "" + f"Leak detected in {event.village}"
    return {"ok": True, "alert": alert}

@app.get("/groundwater/summary")
async def groundwater_summary():
    from collections import defaultdict
    totals: Dict[str, float] = defaultdict(float)
    leaks: Dict[str, int] = defaultdict(int)
    for ev in GROUNDWATER:
        totals[ev.village] += ev.usage_liters
        if ev.leak_detected:
            leaks[ev.village] += 1
    # Convert defaultdicts to plain dicts for JSON serialization
    return {"totals": dict(totals), "leaks": dict(leaks)}

import requests
import json
import hashlib
import time
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=10)
    
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # API chuẩn Vaisala
    api_url = (
        f"https://evntools.com/api/lightning/geojson?start_time={start_time}&end_time={end_time}"
        f"&limit=50000&min_lat=21.4543&max_lat=22.5379&min_lon=103.7878&max_lon=105.2957"
    )

    headers = {"User-Agent": "Mozilla/5.0"}
    FIREBASE_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # 1. TẢI DỮ LIỆU CŨ TỪ FIREBASE
    db_data = {}
    try:
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    # 2. HÚT DỮ LIỆU TỪ VAISALA
    try:
        response = requests.get(api_url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            
            updates = {}
            diem_moi = 0
            diem_cap_nhat = 0
            
            for feature in features:
                props = feature.get("properties", {})
                geom = feature.get("geometry", {})
                if not geom or not props: continue
                
                # --- ĐÃ BỎ LỆNH LỌC type != 0, LẤY TẤT CẢ ---
                
                coords = geom.get("coordinates", [])
                lng, lat = coords[0], coords[1]
                nguon = props.get("source", "Vaisala").title()
                time_str = props.get("timestamp", props.get("time"))
                giatri = abs(float(props.get("amplitude", 0)))
                loaiset = props.get("type", "Cloud/Ground") # Lưu loại sét để sau này bác lọc trên Web
                
                key = hashlib.md5(f"{time_str}_{lat}_{lng}".encode()).hexdigest()
                
                if key in db_data:
                    if db_data[key].get("giatri", 0) == 0 and giatri > 0:
                        updated_record = db_data[key].copy()
                        updated_record["giatri"] = giatri
                        updates[key] = updated_record
                        db_data[key] = updated_record
                        diem_cap_nhat += 1
                else:
                    updates[key] = {
                        "lat": lat, "lng": lng, "giatri": giatri, 
                        "timestamp": time_str, "src": nguon, "type": loaiset, "a": False
                    }
                    db_data[key] = updates[key]
                    diem_moi += 1

            # 3. DỌN RÁC (Quá 7 ngày)
            current_ts = int(now.timestamp())
            seven_days_ago = current_ts - 604800
            diem_xoa = 0
            for k, v in db_data.items():
                try:
                    dt = datetime.strptime(v.get("timestamp"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    if dt.timestamp() < seven_days_ago:
                        updates[k] = None
                        diem_xoa += 1
                except: continue
            
            if updates:
                requests.patch(FIREBASE_URL, json=updates, timeout=60)
                print(f"✅ Full Data: {diem_moi} điểm mới, {diem_cap_nhat} điểm cập nhật, dọn {diem_xoa} rác.")
            else:
                print("✅ Không có dữ liệu mới.")
        else:
            print(f"❌ Lỗi API Vaisala (HTTP {response.status_code})")
    except Exception as e:
        print(f"❌ Lỗi mạng: {e}")

if __name__ == "__main__":
    crawl_lightning_data()

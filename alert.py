import requests
import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta

# ==============================================================================
# CẤU HÌNH BOT CẢNH BÁO
# ==============================================================================
TELEGRAM_BOT_TOKEN = "8793144066:AAGL6xHoVM4aGzNyxBgSubsNaK-hztwn36w"
TELEGRAM_CHAT_ID = "-5111679075"
KHOANG_CACH_MAX = 150 # Chỉ báo động nếu <= 150 mét

GRID_FILES = {
    "Văn Bàn": "vanban.json", "Lào Cai": "laocai.json", "SaPa": "sapa.json",
    "Bát Xát": "batxat.json", "Bắc Hà": "bacha.json", "Bảo Thắng": "baothang.json",
    "Bảo Yên": "baoyen.json", "Mường Khương": "muongkhuong.json", "Yên Bái": "yenbai.json",
    "Trấn Yên": "tranyen.json", "Văn Yên": "vanyen.json", "Lục Yên": "lucyen.json",
    "Nghĩa Lộ": "nghialo.json", "Cao Thế LC": "caothelc.json", "Cao Thế YB": "caotheyb.json"
}

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2 - lat1)/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1)/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

SPATIAL_INDEX = {}
CELL_SIZE = 0.05 

def get_cell_key(lat, lng):
    return (int(lat / CELL_SIZE), int(lng / CELL_SIZE))

def build_spatial_index():
    global SPATIAL_INDEX
    for region, filename in GRID_FILES.items():
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for feature in data.get("features", []):
                        geom = feature.get("geometry", {})
                        if geom and geom.get("type") in ["Point", "MultiPoint"]:
                            coords = geom.get("coordinates", [])
                            if geom.get("type") == "Point" and len(coords) >= 2:
                                pole_lng, pole_lat = coords[0], coords[1]
                            elif geom.get("type") == "MultiPoint" and len(coords) > 0:
                                pole_lng, pole_lat = coords[0][0], coords[0][1]
                            else: continue
                            
                            cell = get_cell_key(pole_lat, pole_lng)
                            if cell not in SPATIAL_INDEX: SPATIAL_INDEX[cell] = []
                            SPATIAL_INDEX[cell].append({
                                "lat": pole_lat, "lng": pole_lng, "region": region.upper(), "props": feature.get("properties", {})
                            })
            except Exception: pass 

def find_nearest_pole_fast(lat, lng):
    nearest_pole, nearest_dist, detected_region = "Không xác định", float('inf'), "LÀO CAI - YÊN BÁI"
    center_cell = get_cell_key(lat, lng)
    cells_to_check = [(center_cell[0]+dx, center_cell[1]+dy) for dx in [-1, 0, 1] for dy in [-1, 0, 1]]
    
    for cell in cells_to_check:
        if cell in SPATIAL_INDEX:
            for pole in SPATIAL_INDEX[cell]:
                dist = haversine_distance(lat, lng, pole["lat"], pole["lng"])
                if dist < nearest_dist:
                    nearest_dist, detected_region = dist, pole["region"]
                    props = pole["props"]
                    ten = props.get("tenDoiTuon", props.get("TenDoiTuong", props.get("tenDoiTuong", props.get("TEN_DOI_TUONG", ""))))
                    so_hieu = props.get("soHieu", props.get("SoHieu", props.get("SO_HIEU", "")))
                    if ten and so_hieu: nearest_pole = f"{ten} ({so_hieu})"
                    elif ten: nearest_pole = ten
                    elif so_hieu: nearest_pole = f"Số: {so_hieu}"
                    else: nearest_pole = "Cột chưa đặt tên"
    return detected_region, nearest_pole, nearest_dist

def send_telegram(message):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def process_alerts():
    FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    try:
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        db_data = fb_response.json() if fb_response.status_code == 200 else {}
    except Exception as e:
        sys.exit(1)

    if not db_data: return

    build_spatial_index()
    updates = {}
    
    for key, strike in db_data.items():
        # Chỉ xử lý nếu điểm sét có cờ da_canh_bao là False
        if strike and isinstance(strike, dict) and strike.get("da_canh_bao") is False:
            lat, lng = strike.get("lat"), strike.get("lng")
            loaiset = strike.get("loaiset", 0)
            giatri = strike.get("giatri", 0)
            ts = strike.get("timestamp", 0)
            
            # Cờ lật sang True ngay lập tức để lần sau không đọc lại
            updated_strike = strike.copy()
            updated_strike["da_canh_bao"] = True
            updates[key] = updated_strike
            
            # Lọc Sét Mặt Đất (loaiset == 0) và nằm trong vùng LC-YB
            if loaiset == 0 and (21.23 <= lat <= 22.85) and (103.50 <= lng <= 105.00):
                vung_quan_ly, ten_cot, khoang_cach = find_nearest_pole_fast(lat, lng)
                
                # Kiểm tra <= 150m
                if khoang_cach <= KHOANG_CACH_MAX:
                    dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=7)))
                    time_str = dt.strftime("%H:%M:%S ngày %d/%m")
                    intensity = f"{giatri} kA" if giatri > 0 else "Chưa xác định"
                    
                    msg = (
                        f"🚨 *[SỰ CỐ TIỀM ẨN] ĐIỆN LỰC {vung_quan_ly}*\n"
                        f"▪️ *Thời gian:* {time_str}\n"
                        f"▪️ *Tọa độ:* `{lat:.4f}, {lng:.4f}`\n"
                        f"▪️ *Loại:* Xuống đất (CG) 🔴 | *Cường độ:* {intensity}\n"
                        f"▪️ *📍 Cột bị đe dọa:* {ten_cot} (Cách {khoang_cach:.1f} mét 🔥)"
                    )
                    send_telegram(msg)

    # Cập nhật các điểm đã xử lý lên Firebase (lưu cờ da_canh_bao = True)
    if updates:
        requests.patch(FIREBASE_URL, json=updates, timeout=60)
        print(f"Đã xử lý cảnh báo và lật cờ cho {len(updates)} điểm sét.")
    else:
        print("Không có điểm sét mới nào cần xử lý.")

if __name__ == "__main__":
    process_alerts()

import requests
import json
import time
import sys
import re
import hashlib
import math
import os
from datetime import datetime, timezone

# ==============================================================================
# CẤU HÌNH ĐƯỜNG TRUYỀN TELEGRAM
# ==============================================================================
TELEGRAM_BOT_TOKEN = "8793144066:AAGL6xHoVM4aGzNyxBgSubsNaK-hztwn36w"
TELEGRAM_CHAT_ID = "-5111679075"

# ==============================================================================
# CÔNG TẮC LỌC SÉT BÁO QUA TELEGRAM (Chọn 1 trong 3 chế độ)
# "ALL" : Báo cáo mọi loại sét (Mặt đất + Trong mây)
# "CG"  : CHỈ báo cáo sét mặt đất (Nguy hiểm cho lưới điện)
# "IC"  : CHỈ báo cáo sét trong mây
# ==============================================================================
LOAI_SET_CANH_BAO = "CG"

# ==============================================================================
# DANH SÁCH FILE JSON LƯỚI ĐIỆN ĐÃ CÓ SẴN TRÊN GITHUB
# ==============================================================================
GRID_FILES = {
    "Văn Bàn": "vanban.json",
    "Lào Cai": "laocai.json",
    "SaPa": "sapa.json",
    "Bát Xát": "batxat.json",
    "Bắc Hà": "bacha.json",
    "Bảo Thắng": "baothang.json",
    "Bảo Yên": "baoyen.json",
    "Mường Khương": "muongkhuong.json",
    "Yên Bái": "yenbai.json",
    "Trấn Yên": "tranyen.json",
    "Văn Yên": "vanyen.json",
    "Lục Yên": "lucyen.json",
    "Nghĩa Lộ": "nghialo.json",
    "Cao Thế LC": "caothelc.json",
    "Cao Thế YB": "caotheyb.json"
}

def haversine_distance(lat1, lon1, lat2, lon2):
    """Tính khoảng cách (mét) giữa 2 tọa độ trên mặt cầu Trái Đất"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def load_grid_data():
    grids = {}
    for region, filename in GRID_FILES.items():
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    grids[region] = json.load(f)
            except Exception:
                pass 
    return grids

def find_nearest_pole(lat, lng, grids):
    nearest_pole = "Không xác định / Chưa có dữ liệu lưới"
    nearest_distance = float('inf')
    detected_region = "LÀO CAI - YÊN BÁI (CHUNG)"
    
    for region, geojson in grids.items():
        features = geojson.get("features", [])
        for feature in features:
            geom = feature.get("geometry", {})
            if geom and geom.get("type") in ["Point", "MultiPoint"]:
                coords = geom.get("coordinates", [])
                if geom.get("type") == "Point" and len(coords) >= 2:
                    pole_lng, pole_lat = coords[0], coords[1]
                elif geom.get("type") == "MultiPoint" and len(coords) > 0:
                    pole_lng, pole_lat = coords[0][0], coords[0][1]
                else:
                    continue
                
                dist = haversine_distance(lat, lng, pole_lat, pole_lng)
                if dist < nearest_distance:
                    nearest_distance = dist
                    detected_region = region.upper()
                    
                    props = feature.get("properties", {})
                    ten = props.get("tenDoiTuon", props.get("TenDoiTuong", props.get("tenDoiTuong", props.get("TEN_DOI_TUONG", ""))))
                    so_hieu = props.get("soHieu", props.get("SoHieu", props.get("SO_HIEU", "")))
                    
                    if ten and so_hieu: nearest_pole = f"{ten} (Số hiệu: {so_hieu})"
                    elif ten: nearest_pole = ten
                    elif so_hieu: nearest_pole = f"Số hiệu: {so_hieu}"
                    else: nearest_pole = "Cột chưa đặt tên"

    return detected_region, nearest_pole, nearest_distance

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or "ĐIỀN_" in TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown" }
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def crawl_lightning_data():
    current_ts = int(time.time())
    source_url = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}" 
    proxy_url = f"https://api.allorigins.win/raw?url={source_url}&disableCache=true"
    headers = { "User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache" }
    FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    
    grid_data = load_grid_data()
    print(f"Đã nạp lưới điện của {len(grid_data)} khu vực: {list(grid_data.keys())}")
    
    db_data = {}
    try:
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except: pass

    try:
        use_proxy = False
        try:
            response = requests.get(source_url, headers=headers, timeout=15)
            if response.status_code != 200: use_proxy = True
        except: use_proxy = True

        if use_proxy: response = requests.get(proxy_url, headers=headers, timeout=60)

        if response.status_code == 200:
            raw_text = response.text
            diem_moi = 0
            diem_cap_nhat = 0
            updates = {} 
            
            blocks = re.findall(r'\{[^{}]*\}', raw_text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            
            for block in valid_blocks:
                try:
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                    
                    if not (6.5 <= lat <= 23.5 and 102.0 <= lng <= 117.5): continue
                    
                    giatri = float(re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1)) if re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE) else 0.0
                    loaiset = int(re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1)) if re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE) else 0
                    
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    giay = int(re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1)) if re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE) else 0
                    
                    dt = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=timezone.utc)
                    ts = dt.timestamp()
                    key = hashlib.md5(f"{ts}_{lat}_{lng}".encode()).hexdigest()
                    
                    # KIỂM TRA ĐIỀU KIỆN GỬI TELEGRAM
                    is_lao_cai_yb = (21.23 <= lat <= 22.85) and (103.50 <= lng <= 105.00)
                    local_hour = (gio + 7) % 24
                    time_alert_str = f"{local_hour:02d}:{phut:02d}:{giay:02d} ngày {ngay:02d}/{thang:02d}"
                    
                    loai_hien_tai = "IC" if loaiset == 1 else "CG"
                    type_str = "Trong mây (IC) ☁️" if loai_hien_tai == "IC" else "Xuống đất (CG) 🔴"
                    intensity_str = f"{giatri} kA" if giatri > 0 else "Chưa xác định"

                    # So sánh với công tắc đã cài đặt
                    cho_phep_bao_dong = False
                    if LOAI_SET_CANH_BAO == "ALL" or LOAI_SET_CANH_BAO == loai_hien_tai:
                        cho_phep_bao_dong = True

                    if key not in db_data:
                        updates[key] = {"lat": lat, "lng": lng, "giatri": giatri, "loaiset": loaiset, "timestamp": ts, "is_new_format": True}
                        db_data[key] = updates[key] 
                        diem_moi += 1
                        
                        if is_lao_cai_yb and cho_phep_bao_dong:
                            vung_quan_ly, ten_cot, khoang_cach = find_nearest_pole(lat, lng, grid_data)
                            dist_str = f"{khoang_cach:.1f} mét" if khoang_cach != float('inf') else "N/A"
                            alert_msg = (
                                f"🚨 *[ĐIỆN LỰC {vung_quan_ly}] PHÁT HIỆN SÉT ĐÁNH*\n"
                                f"▪️ *Thời gian:* {time_alert_str}\n"
                                f"▪️ *Tọa độ:* `{lat:.4f}, {lng:.4f}`\n"
                                f"▪️ *Loại:* {type_str} | *Cường độ:* {intensity_str}\n"
                                f"▪️ *📍 Cột gần nhất:* {ten_cot} (Cách {dist_str})"
                            )
                            send_telegram_alert(alert_msg)
                            
                    else:
                        old_giatri = db_data[key].get("giatri", 0)
                        if (old_giatri == 0 or old_giatri == 0.0) and giatri > 0:
                            updated_record = db_data[key].copy()
                            updated_record["giatri"] = giatri
                            updated_record["loaiset"] = loaiset
                            updates[key] = updated_record
                            db_data[key] = updated_record
                            diem_cap_nhat += 1
                            
                            if is_lao_cai_yb and cho_phep_bao_dong:
                                vung_quan_ly, ten_cot, khoang_cach = find_nearest_pole(lat, lng, grid_data)
                                update_msg = (
                                    f"📊 *[CẬP NHẬT kA] ĐIỆN LỰC {vung_quan_ly}*\n"
                                    f"▪️ *Tia sét lúc:* {time_alert_str}\n"
                                    f"▪️ *Cường độ đo được:* `{giatri} kA` 🔥\n"
                                    f"▪️ *📍 Cột bị ảnh hưởng:* {ten_cot}"
                                )
                                send_telegram_alert(update_msg)
                            
                except Exception: continue 
            
            seven_days_ago = current_ts - 604800
            for k, v in db_data.items():
                if v.get("timestamp", 0) < seven_days_ago: updates[k] = None 
            
            if updates: requests.patch(FIREBASE_URL, json=updates, timeout=60)
        else: sys.exit(1)
    except: sys.exit(1)

if __name__ == "__main__":
    crawl_lightning_data()

import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG V15 (MÔ HÌNH KHO ĐỆM & KHO CHÍNH)...")
    
    now_utc = datetime.now(timezone.utc)
    past_utc = now_utc - timedelta(minutes=90) # Vẫn quét 90 phút để vét sạch
    
    end_time = now_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    current_ts = int(now_utc.timestamp())

    url_hymetnet = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}"
    proxy_hymetnet = f"https://api.allorigins.win/raw?url={url_hymetnet}&disableCache=true"
    
    api_url_vaisala = (
        f"https://evntools.com/api/lightning/geojson?start_time={start_time}&end_time={end_time}"
        f"&limit=50000&min_lat=21.4543&max_lat=22.5379&min_lon=103.7878&max_lon=105.2957"
    )

    FIREBASE_MAIN_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    FIREBASE_BACKUP_URL = "https://datasetweb-duphong-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # Kéo dữ liệu cũ về để chuẩn bị dọn rác
    db_data = {}
    try:
        res = requests.get(FIREBASE_MAIN_URL, timeout=25)
        if res.status_code == 200 and res.json(): db_data = res.json()
    except:
        try:
            res_bk = requests.get(FIREBASE_BACKUP_URL, timeout=25)
            if res_bk.status_code == 200 and res_bk.json(): db_data = res_bk.json()
        except: pass

    updates = {}
    so_luong_temp = 0
    so_luong_full = 0

    def phan_luong_set(lat, lng, giatri, loaiset, ts, nguon):
        nonlocal so_luong_temp, so_luong_full
        
        ts_int = int(ts)
        key = hashlib.md5(f"{ts_int}_{round(lat,4)}_{round(lng,4)}".encode()).hexdigest()
        
        data_packet = {
            "lat": lat, "lng": lng, "giatri": giatri,
            "loaiset": loaiset, "timestamp": ts_int,
            "src": nguon, "is_new_format": True
        }

        # ĐIỀU KIỆN PHÂN LUỒNG
        is_rounded_time = (ts_int % 60 == 0)
        is_no_amplitude = (giatri == 0 or giatri == 0.0)

        if is_rounded_time or is_no_amplitude:
            # Dữ liệu thô -> Ném vào kho tạm (temp)
            updates[f"temp/{key}"] = data_packet
            so_luong_temp += 1
        else:
            # Dữ liệu sạch -> Ném vào kho chính (full)
            updates[f"full/{key}"] = data_packet
            so_luong_full += 1

    # =======================================================
    # Quét Hymetnet
    try:
        res_h = requests.get(proxy_hymetnet, timeout=20)
        if res_h.status_code == 200:
            blocks = re.findall(r'\{[^{}]*\}', res_h.text)
            for block in [b for b in blocks if 'lat' in b.lower()]:
                try:
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                    if not (21.40 <= lat <= 22.60 and 103.70 <= lng <= 105.30): continue
                        
                    g_m = re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    giatri = float(g_m.group(1)) if g_m else 0.0
                    l_m = re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    loaiset = int(l_m.group(1)) if l_m else 0
                    
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    giay_m = re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    giay = int(giay_m.group(1)) if giay_m else 0
                    
                    ts = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=timezone.utc).timestamp()
                    if current_ts - ts <= 5400: 
                        phan_luong_set(lat, lng, giatri, loaiset, ts, "Hymetnet")
                except: continue
    except: pass

    # =======================================================
    # Quét EVNTools
    for attempt in range(2):
        try:
            res_v = requests.get(api_url_vaisala, timeout=20)
            if res_v.status_code == 200:
                for f in res_v.json().get("features", []):
                    p = f.get("properties", {})
                    coords = f.get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        giatri = abs(float(p.get("amplitude", 0)))
                        try: ts_str = p.get("timestamp", p.get("time"))
                        except: continue
                        try: ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
                        except:
                            try: ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                            except: continue
                        phan_luong_set(coords[1], coords[0], giatri, p.get("type", 0), ts, p.get("source", "Vaisala").title())
                break
        except: time.sleep(3)

   # =======================================================
    # DỌN RÁC THEO 2 TIÊU CHÍ KHÁC NHAU
    # =======================================================
    xoa_temp = 0
    xoa_full = 0
    
    # 70 phút (Sống đủ lâu để cover độ trễ 60 phút của EVN/Hymetnet)
    seventy_mins_ago = current_ts - 4200 
    
    # 7 ngày (Lưu trữ lịch sử dài hạn)
    seven_days_ago = current_ts - 604800 

    # Dọn kho tạm (temp)
    temp_db = db_data.get("temp", {})
    for k, v in temp_db.items():
        if v and float(v.get("timestamp", 0)) < seventy_mins_ago:
            updates[f"temp/{k}"] = None
            xoa_temp += 1

    # Dọn kho chính (full)
    full_db = db_data.get("full", {})
    for k, v in full_db.items():
        if v and float(v.get("timestamp", 0)) < seven_days_ago:
            updates[f"full/{k}"] = None
            xoa_full += 1

    # ĐẨY DỮ LIỆU
    if updates:
        print(f"🔄 Đang đồng bộ lên 2 kho Firebase...")
        try: requests.patch(FIREBASE_MAIN_URL, json=updates, timeout=30)
        except: pass
        try: requests.patch(FIREBASE_BACKUP_URL, json=updates, timeout=30)
        except: pass
        print(f"✅ Nạp: {so_luong_temp} điểm TẠM | {so_luong_full} điểm CHÍNH THỨC.")
        print(f"🧹 Xóa: {xoa_temp} điểm tạm (>70p) | {xoa_full} điểm cũ (>7 ngày).")
    else:
        print(f"✅ Hệ thống sạch sẽ, không có cập nhật mới.")

if __name__ == "__main__":
    crawl_lightning_data()

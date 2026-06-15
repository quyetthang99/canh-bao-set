import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG V15 (MÔ HÌNH KHO ĐỆM & KHO CHÍNH) - LOGIC PHÂN LUỒNG MỚI...")
    
    now_utc = datetime.now(timezone.utc)
    past_utc = now_utc - timedelta(hours=3) # Quét lùi 3 tiếng (180 phút) để vét sạch dữ liệu trễ
    
    end_time = now_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    current_ts = int(now_utc.timestamp())

    # --- CẤU HÌNH HEADERS CHUẨN ĐỂ TRÁNH BỊ CHẶN (BẮT BUỘC) ---
    headers_standard = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Cache-Control": "no-cache"
    }

    # --- CẤU HÌNH URL NGUỒN ---
    url_hymetnet = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}"
    proxy_hymetnet = f"https://api.allorigins.win/raw?url={url_hymetnet}&disableCache=true"

    # Tọa độ giám sát khu vực Lào Cai
    api_url_vaisala = (
        f"https://evntools.com/api/lightning/geojson?start_time={start_time}&end_time={end_time}"
        f"&limit=50000&min_lat=21.4543&max_lat=22.5379&min_lon=103.7878&max_lon=105.2957"
    )

    FIREBASE_MAIN_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    FIREBASE_BACKUP_URL = "https://datasetweb-duphong-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # 1. TẢI BỘ NHỚ LỊCH SỬ ĐỂ CHUẨN BỊ DỌN RÁC
    db_data = {}
    try:
        print("📥 Đang tải dữ liệu cũ từ Firebase Main...")
        res = requests.get(FIREBASE_MAIN_URL, timeout=25)
        if res.status_code == 200 and res.json(): 
            db_data = res.json()
    except Exception as e:
        print(f"⚠️ Không thể kết nối Firebase Main ({e}). Thử kết nối Kho Dự Phòng...")
        try:
            res_bk = requests.get(FIREBASE_BACKUP_URL, timeout=25)
            if res_bk.status_code == 200 and res_bk.json(): 
                db_data = res_bk.json()
        except Exception as e_bk: 
            print(f"❌ Thất bại khi tải bộ nhớ từ cả 2 kho Firebase: {e_bk}")

    updates = {}
    so_luong_temp = 0
    so_luong_full = 0

    # Hàm xử lý phân luồng sét đất / sét thô
    def phan_luong_set(lat, lng, giatri, loaiset, ts, nguon):
        nonlocal so_luong_temp, so_luong_full
        
        ts_int = int(ts)
        key = hashlib.md5(f"{ts_int}_{round(lat,4)}_{round(lng,4)}".encode()).hexdigest()
        
        data_packet = {
            "lat": lat, "lng": lng, "giatri": giatri,
            "loaiset": loaiset, "timestamp": ts_int,
            "src": nguon, "is_new_format": True
        }

        # Kiểm tra trùng lặp trong database hiện tại để tránh ghi đè dữ liệu cũ
        in_temp = key in db_data.get("temp", {})
        in_full = key in db_data.get("full", {})

        # ĐIỀU KIỆN PHÂN LUỒNG DỮ LIỆU MỚI: CHỈ XÉT CƯỜNG ĐỘ (BỎ XÉT GIÂY CHẴN)
        is_no_amplitude = (giatri == 0 or giatri == 0.0)

        if is_no_amplitude:
            # Không có cường độ -> Đẩy vào kho tạm (temp)
            if not in_temp and f"temp/{key}" not in updates:
                updates[f"temp/{key}"] = data_packet
                so_luong_temp += 1
        else:
            # Có cường độ kA chuẩn -> Đẩy thẳng vào kho chính (full)
            if not in_full and f"full/{key}" not in updates:
                updates[f"full/{key}"] = data_packet
                so_luong_full += 1

    # =======================================================
    # LUỒNG 1: CÀO DỮ LIỆU TỪ HYMETNET (CƠ CHẾ DỰ PHÒNG THÔNG MINH)
    # =======================================================
    print("\n[LUỒNG 1] Đang kết nối máy chủ Hymetnet...")
    try:
        # Thử kết nối trực tiếp trước
        res_h = requests.get(url_hymetnet, headers=headers_standard, timeout=15)
        # Nếu máy chủ chặn hoặc lỗi mạng, chuyển sang đi qua Proxy AllOrigins
        if res_h.status_code != 200:
            print("⚠️ Kết nối trực tiếp Hymetnet không thành công. Đang chuyển hướng qua Proxy...")
            res_h = requests.get(proxy_hymetnet, headers=headers_standard, timeout=25)
            
        if res_h.status_code == 200:
            blocks = re.findall(r'\{[^{}]*\}', res_h.text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower()]
            
            for block in valid_blocks:
                try:
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                
                    # Bộ lọc tọa độ khu vực giám sát Lào Cai
                    if not (21.4543 <= lat <= 22.5379 and 103.7878 <= lng <= 105.2957): 
                        continue

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
                    
                    # Chỉ lấy dữ liệu trong vòng 3 tiếng qua (180 phút * 60 = 10800 giây)
                    if current_ts - ts <= 10800: 
                        phan_luong_set(lat, lng, giatri, loaiset, ts, "Hymetnet")
                except: 
                    continue
            print(f"✅ Đồng bộ xong luồng Hymetnet.")
        else:
            print(f"❌ Luồng Hymetnet thất bại. Mã lỗi HTTP: {res_h.status_code}")
    except Exception as e:
        print(f"❌ Lỗi xử lý luồng Hymetnet: {e}")

    # =======================================================
    # LUỒNG 2: CÀO DỮ LIỆU TỪ VAISALA / EVNTOOLS (CÓ HEADERS)
    # =======================================================
    print("\n[LUỒNG 2] Đang kết nối máy chủ Vaisala (EVNTools)...")
    vaisala_success = False
    for attempt in range(2):
        try:
            res_v = requests.get(api_url_vaisala, headers=headers_standard, timeout=20)
            if res_v.status_code == 200:
                features = res_v.json().get("features", [])
                for f in features:
                    p = f.get("properties", {})
                    coords = f.get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        giatri = abs(float(p.get("amplitude", 0)))
                        try: 
                            ts_str = p.get("timestamp", p.get("time"))
                        except: 
                            continue
                        try: 
                            ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
                        except:
                            try: 
                                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                            except: 
                                continue
                        
                        # Điều hướng phân luồng vào kho tạm hoặc kho chính
                        phan_luong_set(coords[1], coords[0], giatri, p.get("type", 0), ts, p.get("source", "Vaisala").title())
                
                print(f"✅ Đồng bộ xong luồng Vaisala.")
                vaisala_success = True
                break
            elif res_v.status_code == 429:
                print(f"⚠️ Vaisala báo lỗi 429 (Too Many Requests / Chặn IP). Thử lại sau.")
                time.sleep(3)
            else:
                print(f"❌ Luồng Vaisala báo lỗi HTTP: {res_v.status_code}")
                break
        except Exception as e:
            print(f"⚠️ Lỗi kết nối luồng Vaisala lần {attempt + 1}: {e}")
            time.sleep(3)

    # =======================================================
    # 3. DỌN RÁC DATABASE THEO TIÊU CHÍ KHO ĐỆM VÀ KHO LƯU TRỮ
    # =======================================================
    xoa_temp = 0
    xoa_full = 0
    
    don_kho_tam_ago = current_ts - 12600   # Kho tạm dọn sau 210 phút (3.5 tiếng) để cover vòng quét 3 tiếng
    seven_days_ago = current_ts - 604800   # Kho chính lưu lịch sử dài hạn trong 7 ngày

    # Dọn dẹp kho tạm (temp)
    temp_db = db_data.get("temp", {})
    for k, v in temp_db.items():
        if v and float(v.get("timestamp", 0)) < don_kho_tam_ago:
            updates[f"temp/{k}"] = None
            xoa_temp += 1

    # Dọn dẹp kho chính (full)
    full_db = db_data.get("full", {})
    for k, v in full_db.items():
        if v and float(v.get("timestamp", 0)) < seven_days_ago:
            updates[f"full/{k}"] = None
            xoa_full += 1

    # =======================================================
    # 4. ĐỒNG BỘ GÓI PATCH LÊN HỆ THỐNG FIREBASE
    # =======================================================
    if updates:
        print(f"\n🔄 Đang tiến hành đồng bộ dữ liệu lên hệ thống 2 kho Firebase...")
        
        # Đẩy lên kho chính
        try: 
            res_m = requests.patch(FIREBASE_MAIN_URL, json=updates, timeout=30)
            if res_m.status_code != 200: print(f"❌ Lỗi Firebase Main: {res_m.text}")
        except Exception as e: 
            print(f"❌ Lỗi kết nối Firebase Main: {e}")
            
        # Đẩy lên kho dự phòng
        try: 
            res_b = requests.patch(FIREBASE_BACKUP_URL, json=updates, timeout=30)
        except: 
            pass
            
        print(f"✅ VẬN HÀNH HOÀN TẤT!")
        print(f"   + Nạp mới: {so_luong_temp} điểm TẠM | {so_luong_full} điểm CHÍNH THỨC (Có cường độ kA chuẩn).")
        print(f"   + Đã quét sạch: {xoa_temp} điểm tạm quá hạn (>3.5h) | {xoa_full} điểm lịch sử cũ (>7 ngày).")
    else:
        print(f"\n✅ Hệ thống kiểm tra xong. Không phát hiện xung sét mới hoặc rác cần dọn.")

if __name__ == "__main__":
    crawl_lightning_data()

import requests, json, math, os, sys
from datetime import datetime, timezone, timedelta

# Cấu hình
TELEGRAM_BOT_TOKEN = "8793144066:AAGL6xHoVM4aGzNyxBgSubsNaK-hztwn36w"
TELEGRAM_CHAT_ID = "-5111679075"
KHOANG_CACH_MAX = 150 
FIREBASE_URL = "https://databandoset-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"

# ... [Chèn hàm haversine_distance, build_spatial_index, find_nearest_pole_fast ở đây] ...

def send_telegram(message):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def process_alerts():
    # Chỉ lấy dữ liệu chưa cảnh báo (a=False)
    query_url = f"{FIREBASE_URL}?orderBy=%22a%22&equalTo=false"
    try:
        db_data = requests.get(query_url, timeout=30).json() or {}
    except: return

    if not db_data: return

    updates = {}
    now_ts = datetime.now().timestamp()
    
    # Chỉ xử lý các điểm sét trong 10 phút qua (600 giây)
    filtered_data = {k: v for k, v in db_data.items() if v.get("t", 0) > (now_ts - 600)}
    
    if not filtered_data: return
    
    build_spatial_index() 
    
    for key, strike in filtered_data.items():
        lat, lng = strike.get("lat"), strike.get("lng")
        
        # Đánh dấu đã xử lý
        updated_strike = strike.copy()
        updated_strike["a"] = True
        updates[key] = updated_strike
        
        # Đo khoảng cách & Gửi Telegram
        vung, cot, kc = find_nearest_pole_fast(lat, lng)
        if kc <= KHOANG_CACH_MAX:
            # CHUYỂN ĐỔI SANG GIỜ VIỆT NAM (UTC+7)
            dt_vn = datetime.fromtimestamp(strike.get("t"), tz=timezone.utc) + timedelta(hours=7)
            time_str = dt_vn.strftime("%H:%M:%S ngày %d/%m")
            
            msg = (
                f"🚨 *[SỰ CỐ TIỀM ẨN] ĐIỆN LỰC {vung}*\n"
                f"▪️ *Thời gian:* {time_str}\n"
                f"▪️ *Tọa độ:* `{lat:.4f}, {lng:.4f}`\n"
                f"▪️ *Loại:* Xuống đất (CG) 🔴⚡\n"
                f"▪️ *Cường độ:* {strike.get('g', 0)} kA\n"
                f"▪️ *📍 Cột bị đe dọa:* {cot} (Cách {kc:.1f} mét 🔥)\n\n"
                f"🌐 *Xem chi tiết tại:* https://quyetthang99.github.io/canh-bao-set/"
            )
            send_telegram(msg)
    
    if updates: requests.patch(FIREBASE_URL, json=updates, timeout=60)

if __name__ == "__main__": process_alerts()

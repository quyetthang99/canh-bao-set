import requests
import json
import os

def crawl_lightning_data():
    url = "http://hymetnet.gov.vn/dongset"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "http://hymetnet.gov.vn/lightningmaps/"
    }
    
    try:
        # Gửi yêu cầu lấy dữ liệu từ server gốc kèm Header giả lập trình duyệt để tránh bị chặn
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # Ghi dữ liệu vào file duongset.json
            with open("duongset.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print("Cào dữ liệu sét thành công!")
        else:
            print(f"Lỗi tải dữ liệu, mã lỗi: {response.status_code}")
    except Exception as e:
        print(f"Đã xảy ra lỗi khi cào dữ liệu: {e}")

if __name__ == "__main__":
    crawl_lightning_data()
import requests
import time
import sys
import hashlib
from datetime import datetime, timezone, timedelta

FIREBASE_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def crawl_lightning_data():

    current_ts = int(time.time())

    db_data = {}

    try:
        print("Đang tải dữ liệu lịch sử từ Firebase...")

        fb_response = requests.get(
            FIREBASE_URL,
            timeout=30
        )

        if fb_response.status_code == 200:
            data = fb_response.json()

            if data:
                db_data = data

    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    try:

        print("Đang lấy dữ liệu sét từ EVN Tools...")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        url = "https://evntools.com/api/lightning/geojson"

        params = {
            "start_time": start_time.isoformat().replace("+00:00", "Z"),
            "end_time": end_time.isoformat().replace("+00:00", "Z"),
            "limit": 50000,

            # Vùng Lào Cai - Yên Bái
            "min_lat": 21.10,
            "max_lat": 23.00,
            "min_lon": 103.30,
            "max_lon": 105.20
        }

        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=60
        )

        if response.status_code != 200:
            print(f"❌ Lỗi API: {response.status_code}")
            sys.exit(1)

        geojson = response.json()

        features = geojson.get("features", [])

        print(f"Tìm thấy {len(features)} điểm sét")

        updates = {}

        diem_moi = 0
        diem_cap_nhat = 0
        diem_bi_loai = 0

        for feature in features:

            try:

                geometry = feature.get("geometry", {})
                properties = feature.get("properties", {})

                coords = geometry.get("coordinates")

                if not coords or len(coords) < 2:
                    continue

                lng = float(coords[0])
                lat = float(coords[1])

                if not (
                    21.10 <= lat <= 23.00
                    and 103.30 <= lng <= 105.20
                ):
                    diem_bi_loai += 1
                    continue

                timestamp_str = properties.get("timestamp")

                if not timestamp_str:
                    continue

                dt = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )

                ts = dt.timestamp()

                giatri = properties.get("giatri")

                if giatri is None:
                    giatri = 0

                loaiset = properties.get("loaiset", 0)

                key_string = f"{ts}_{lat}_{lng}"
                key = hashlib.md5(
                    key_string.encode()
                ).hexdigest()

                if key not in db_data:

                    record = {
                        "lat": lat,
                        "lng": lng,
                        "giatri": giatri,
                        "loaiset": loaiset,
                        "timestamp": ts,
                        "source": properties.get("source", "vaisala"),
                        "is_new_format": True
                    }

                    updates[key] = record
                    db_data[key] = record

                    diem_moi += 1

                else:

                    old_giatri = db_data[key].get(
                        "giatri",
                        0
                    )

                    if (
                        (old_giatri == 0 or old_giatri == 0.0)
                        and giatri > 0
                    ):

                        updated_record = db_data[key].copy()

                        updated_record["giatri"] = giatri
                        updated_record["loaiset"] = loaiset

                        updates[key] = updated_record
                        db_data[key] = updated_record

                        diem_cap_nhat += 1

            except Exception:
                continue

        print(
            f"Đã LỌC BỎ {diem_bi_loai} điểm ngoài vùng Lào Cai - Yên Bái."
        )

        seven_days_ago = current_ts - 604800

        diem_xoa = 0

        for k, v in list(db_data.items()):

            if v.get("timestamp", 0) < seven_days_ago:

                updates[k] = None
                diem_xoa += 1

        if updates:

            print(
                f"Đang đẩy/xóa dữ liệu lên Firebase ({len(updates)} tác vụ)..."
            )

            patch_response = requests.patch(
                FIREBASE_URL,
                json=updates,
                timeout=60
            )

            if patch_response.status_code == 200:

                print(
                    f"✅ HOÀN TẤT! "
                    f"Đã lưu {diem_moi} điểm mới. "
                    f"Bổ sung {diem_cap_nhat} điểm. "
                    f"Đã dọn {diem_xoa} điểm cũ."
                )

            else:

                print(
                    f"❌ Lỗi Firebase: {patch_response.text}"
                )

                sys.exit(1)

        else:

            print(
                "✅ Không có dữ liệu mới để cập nhật."
            )

    except Exception as e:

        print(f"❌ Lỗi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    crawl_lightning_data()

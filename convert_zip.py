import os
import glob
import geopandas as gpd
import pandas as pd
import tempfile
import zipfile

# Quét tìm TẤT CẢ các file .zip có trong thư mục
zip_files = glob.glob("*.zip")

if not zip_files:
    print("Không tìm thấy file .zip nào để xử lý.")
else:
    print(f"Tìm thấy {len(zip_files)} file .zip. Bắt đầu chuyển đổi hàng loạt...")

# Xử lý từng file zip một
for zip_file in zip_files:
    # Lấy tên gốc của file zip. Ví dụ: 'laocai.zip' -> 'laocai'
    base_name = os.path.splitext(zip_file)[0]
    
    # Tạo tên file output JSON tương ứng. Ví dụ: 'laocai.json'
    out_json = f"{base_name}.json"

    print(f"\n▶ Đang xử lý: {zip_file} -> Xuất ra: {out_json}")

    try:
        # Tạo thư mục tạm để giải nén an toàn
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)

            # Quét tất cả các file .shp bên trong
            shp_files = glob.glob(os.path.join(tmpdir, "**", "*.shp"), recursive=True)

            if not shp_files:
                print(f"  [Cảnh báo] Không có Shapefile (.shp) nào trong {zip_file}")
                continue

            print(f"  Đã tìm thấy {len(shp_files)} lớp dữ liệu. Đang gộp...")

            gdf_list = []
            for shp in shp_files:
                try:
                    gdf = gpd.read_file(shp)
                    # Chuyển hệ tọa độ về chuẩn WGS84 cho bản đồ Web
                    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
                        gdf = gdf.to_crs(epsg=4326)
                    gdf_list.append(gdf)
                except Exception as e:
                    print(f"  - [Bỏ qua] Lớp {os.path.basename(shp)} bị lỗi: {e}")

            # Gộp tất cả và xuất ra GeoJSON
            if gdf_list:
                merged_gdf = pd.concat(gdf_list, ignore_index=True)
                merged_gdf = gpd.GeoDataFrame(merged_gdf, geometry='geometry')
                merged_gdf.to_file(out_json, driver="GeoJSON")
                print(f"  ✅ THÀNH CÔNG: Đã tạo ra file {out_json}")
            else:
                print(f"  [Cảnh báo] File {zip_file} không có dữ liệu hợp lệ.")

    except Exception as e:
        print(f"  [Lỗi hệ thống] {zip_file}: {e}")

print("\n🎉 HOÀN TẤT TOÀN BỘ QUÁ TRÌNH!")

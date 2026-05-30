import os
import glob
import geopandas as gpd
import pandas as pd
import tempfile
import zipfile

# Quét tìm TẤT CẢ các file .zip có trong thư mục hiện tại
zip_files = glob.glob("*.zip")

if not zip_files:
    print("Không tìm thấy file .zip nào để xử lý.")
else:
    print(f"Tìm thấy {len(zip_files)} file .zip. Bắt đầu quá trình chuyển đổi hàng loạt...")

for zip_file in zip_files:
    # Lấy tên gốc của file zip (VD: 'lucyen.zip' -> 'lucyen')
    base_name = os.path.splitext(zip_file)[0]
    
    # Giữ nguyên quy tắc cũ cho file Văn Bàn để không lỗi web, các huyện khác lấy đúng tên
    if base_name == "luoi_dien":
        out_json = "luoidien.json"
    else:
        out_json = f"{base_name}.json"

    print(f"\n▶ Đang xử lý file: {zip_file} -> Xuất ra: {out_json}")

    try:
        # Tạo thư mục tạm thời để giải nén an toàn
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)

            # Tìm tất cả các lớp bản đồ .shp bên trong file zip
            shp_files = glob.glob(os.path.join(tmpdir, "**", "*.shp"), recursive=True)

            if not shp_files:
                print(f"  [Cảnh báo] Không tìm thấy lớp Shapefile (.shp) nào trong {zip_file}")
                continue

            print(f"  Đã tìm thấy {len(shp_files)} lớp dữ liệu (Cột, Trạm, Đoạn dây...). Đang gộp...")

            gdf_list = []
            for shp in shp_files:
                try:
                    # Đọc file shp
                    gdf = gpd.read_file(shp)
                    
                    # Ép chuẩn tọa độ về WGS84 (EPSG:4326) để hiển thị chuẩn trên bản đồ web
                    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
                        gdf = gdf.to_crs(epsg=4326)
                        
                    gdf_list.append(gdf)
                    print(f"  - Đã xử lý xong: {os.path.basename(shp)}")
                except Exception as e:
                    print(f"  - [Bỏ qua] Lớp {os.path.basename(shp)} bị lỗi hoặc trống: {e}")

            # Tiến hành gộp và xuất ra GeoJSON
            if gdf_list:
                merged_gdf = pd.concat(gdf_list, ignore_index=True)
                merged_gdf = gpd.GeoDataFrame(merged_gdf, geometry='geometry')
                merged_gdf.to_file(out_json, driver="GeoJSON")
                print(f"  ✅ Tuyệt vời! Đã nén toàn bộ hạ tầng vào {out_json} thành công.")
            else:
                print(f"  [Cảnh báo] File {zip_file} không có dữ liệu hợp lệ để gộp.")

    except Exception as e:
        print(f"  [Lỗi hệ thống] Khi xử lý {zip_file}: {e}")

print("\n🎉 KẾT THÚC QUÁ TRÌNH CHUYỂN ĐỔI.")import geopandas as gpd
import pandas as pd
import os
import zipfile
import glob

def process_zipped_shapefile():
    zip_filename = "luoi_dien.zip" 
    output_json = "luoidien.json"
    extract_dir = "temp_shp_extracted" # Thư mục tạm để giải nén

    if not os.path.exists(zip_filename):
        print(f"Hệ thống đang chờ bạn upload file {zip_filename} lên...")
        return

    try:
        print(f"Đang giải nén toàn bộ file {zip_filename}...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Quét tìm tất cả các file .shp vừa được giải nén ra
        shp_files = glob.glob(f"{extract_dir}/**/*.shp", recursive=True)
        
        if not shp_files:
            print("Lỗi: Không tìm thấy bất kỳ file .shp nào trong file nén!")
            return
            
        print(f"Đã tìm thấy {len(shp_files)} lớp dữ liệu (Cột, Trạm, Khoảng cột...). Đang gộp...")
        
        # Thông số hệ tọa độ với kinh tuyến trục cực chuẩn xác (104° 45' 03" = 104.750833)
        vn2000_crs = "+proj=tmerc +lat_0=0 +lon_0=104.750833 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
        
        danh_sach_gdfs = []
        for shp in shp_files:
            try:
                gdf = gpd.read_file(shp)
                # Ép hệ tọa độ VN2000
                if gdf.crs is None:
                    gdf.set_crs(vn2000_crs, inplace=True)
                
                # Chuyển đổi sang WGS-84 dùng cho bản đồ Web
                gdf_wgs84 = gdf.to_crs(epsg=4326)
                danh_sach_gdfs.append(gdf_wgs84)
                print(f" - Đã xử lý xong: {os.path.basename(shp)}")
            except Exception as e:
                print(f" - Bỏ qua lớp {os.path.basename(shp)} do lỗi: {e}")
        
        # Gộp tất cả các mảng dữ liệu lại với nhau
        if danh_sach_gdfs:
            combined_gdf = pd.concat(danh_sach_gdfs, ignore_index=True)
            combined_gdf.to_file(output_json, driver="GeoJSON")
            print("✅ Tuyệt vời! Đã nén toàn bộ hạ tầng lưới điện vào luoidien.json vĩnh viễn.")
        else:
            print("❌ Không có dữ liệu hợp lệ để xuất.")
            
    except Exception as e:
        print(f"❌ Quá trình chạy bị lỗi: {e}")

if __name__ == "__main__":
    process_zipped_shapefile()

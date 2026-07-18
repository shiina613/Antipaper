import os

from huggingface_hub import hf_hub_download


def download_yolo_table_weights() -> None:
    # Tạo thư mục models nếu chưa có
    os.makedirs("models", exist_ok=True)

    print("Đang tải YOLOv8 Table Detection weights từ Hugging Face...")

    # Sử dụng bộ weights fine-tune của cộng đồng (keremberke/yolov8m-table-extraction)
    # Đây là bản Medium (m), cân bằng tốt giữa tốc độ và độ chính xác cho MVP.
    model_path = hf_hub_download(
        repo_id="keremberke/yolov8m-table-extraction",
        filename="best.pt",
        local_dir="models",
        local_dir_use_symlinks=False,
    )

    # Đổi tên file cho dễ quản lý
    final_path = os.path.join("models", "table_detect_yolov8.pt")
    if os.path.exists(model_path) and model_path != final_path:
        os.rename(model_path, final_path)

    print(f"Tải thành công! File lưu tại: {final_path}")


if __name__ == "__main__":
    download_yolo_table_weights()

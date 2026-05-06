from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
import numpy as np
from PIL import Image

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "✅ API is online — Auto-Crop Mode"}

def auto_crop_whitespace(img: Image.Image, padding: int = 4) -> Image.Image:
    """
    ตัดพื้นที่สีขาว/ว่างรอบตารางออกอัตโนมัติ
    - padding: จำนวน pixel ที่เผื่อรอบขอบตาราง (ป้องกันตัดชิดเกิน)
    """
    img_array = np.array(img.convert("RGB"))
    
    # หา pixel ที่ไม่ใช่สีขาว (threshold 250 เพื่อรับ off-white ด้วย)
    non_white_mask = np.any(img_array < 250, axis=2)
    
    rows = np.any(non_white_mask, axis=1)  # แถวที่มีเนื้อหา
    cols = np.any(non_white_mask, axis=0)  # คอลัมน์ที่มีเนื้อหา
    
    if not rows.any():
        return img  # ถ้าหน้าว่างทั้งหมด ส่งคืนเดิม
    
    row_min, row_max = np.where(rows)[0][[0, -1]]
    col_min, col_max = np.where(cols)[0][[0, -1]]
    
    # เพิ่ม padding รอบขอบ
    h, w = img_array.shape[:2]
    row_min = max(0, row_min - padding)
    row_max = min(h - 1, row_max + padding)
    col_min = max(0, col_min - padding)
    col_max = min(w - 1, col_max + padding)
    
    return img.crop((col_min, row_min, col_max + 1, row_max + 1))

@app.post("/convert")
async def convert_to_zip(
    file: UploadFile = File(...),
    names: str = Form(...),
    # ratios ยังรับไว้ได้ (backward compatible) แต่ไม่ใช้แล้ว
    ratios: str = Form(default=""),
    scale: float = Form(default=3.0),      # ความละเอียดภาพ (3.0 = ~300dpi)
    padding: int = Form(default=4),        # pixel เผื่อรอบขอบ
    output_format: str = Form(default="png")  # "png" หรือ "jpg"
):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        name_list = [n.strip() for n in names.split(",")]
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(len(doc)):
                page = doc.load_page(i)
                mat = fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat)
                
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                
                # Auto-crop พื้นที่ขาวออก
                img_cropped = auto_crop_whitespace(img, padding=padding)
                
                out_bytes = io.BytesIO()
                fmt = output_format.lower()
                if fmt in ("jpg", "jpeg"):
                    img_cropped = img_cropped.convert("RGB")
                    img_cropped.save(out_bytes, format="JPEG", quality=95)
                    ext = "jpg"
                else:
                    img_cropped.save(out_bytes, format="PNG")
                    ext = "png"
                
                name = name_list[i] if i < len(name_list) else f"page_{i+1}"
                zip_file.writestr(f"{name}.{ext}", out_bytes.getvalue())
        
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
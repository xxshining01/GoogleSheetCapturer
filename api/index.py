from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image, ImageChops

app = FastAPI()

# ฟังก์ชันหั่นเฉพาะขอบล่างแบบ Zero Edge (ชิดเส้นตาราง 100%)
def trim_bottom_white_space(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    
    if bbox:
        # bbox[3] คือพิกัดแนวตั้งของ "พิกเซลล่างสุด" ที่มีสี (เส้นตารางเส้นสุดท้าย)
        # สั่งตัดแบบชิดเส้นพิกัดนี้เป๊ะๆ ไม่บวกพื้นที่ขาวเผื่ออีกต่อไป
        img = img.crop((0, 0, img.width, bbox[3]))
    
    out_bytes = io.BytesIO()
    img.save(out_bytes, format="PNG")
    return out_bytes.getvalue()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (Absolute Zero Edge Bottom Mode)!"}

@app.post("/api")
async def convert_to_zip(file: UploadFile = File(...), names: str = Form(...)):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        name_list = [n.strip() for n in names.split(",")]
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(len(doc)):
                page = doc.load_page(i)
                mat = fitz.Matrix(3.0, 3.0) # ความละเอียดภาพคมชัดสูง
                pix = page.get_pixmap(matrix=mat)
                
                cropped_png_bytes = trim_bottom_white_space(pix.tobytes("png"))
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, cropped_png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})
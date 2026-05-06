from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image, ImageChops

app = FastAPI()

# ฟังก์ชันหั่นเฉพาะพื้นที่ว่าง "ด้านล่าง" (รักษาสัดส่วนซ้ายขวาให้เท่ากันทุกรูป)
def trim_bottom_white_space(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    
    if bbox:
        # bbox คือ (ซ้าย, บน, ขวา, ล่าง)
        # เราจะครอบภาพตั้งแต่ ซ้ายสุด(0), บนสุด(0), ขวาสุด(img.width) และตัดแค่ด้านล่าง(bbox[3])
        # บวกเพิ่ม 2 pixel กันเส้นขอบตารางล่างสุดแหว่ง
        bottom = min(bbox[3] + 2, img.height)
        img = img.crop((0, 0, img.width, bottom))
    
    out_bytes = io.BytesIO()
    img.save(out_bytes, format="PNG")
    return out_bytes.getvalue()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (Zero Edge & Fixed Width Mode)!"}

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
                mat = fitz.Matrix(3.0, 3.0) # คูณความละเอียดภาพ 3 เท่า ให้คมกริบ
                pix = page.get_pixmap(matrix=mat)
                
                # ส่งภาพเข้าฟังก์ชันหั่นขอบล่าง
                cropped_png_bytes = trim_bottom_white_space(pix.tobytes("png"))
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, cropped_png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})
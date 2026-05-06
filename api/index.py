from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image

app = FastAPI()

# ฟังก์ชันสแกนจาก "บนลงล่าง" (Top-Down Scanner) ทะลวงขยะก้นกระดาษ
def trim_top_down_white_space(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pixels = img.load()
    width, height = img.size
    
    empty_streak = 0
    bottom_crop = height
    
    # 1. เริ่มสแกนจากบรรทัดบนสุด (y=0) ไหลลงไปล่างสุด (y=height)
    for y in range(0, height):
        is_empty = True
        
        # 2. กวาดสายตาแนวนอน (ข้ามขอบกระดาษซ้ายขวาไปฝั่งละ 50 พิกเซล)
        for x in range(50, width - 50, 5):
            r, g, b = pixels[x, y]
            
            # ถ้าเจอสีเข้ม (เส้นขอบตาราง หรือ ตัวหนังสือ) แม้แต่จุดเดียว
            if r < 240 or g < 240 or b < 240:
                is_empty = False
                break # เลิกหาในบรรทัดนี้ ไปบรรทัดต่อไปได้เลย
                
        if is_empty:
            empty_streak += 1  # ถ้านี่คือบรรทัดที่ขาวโล่ง ให้นับสะสมไว้
        else:
            empty_streak = 0   # ถ้าเดินสะดุดเส้นตาราง ให้รีเซ็ตค่าเป็น 0 ทันที
            
        # 3. ถ้าเจอพื้นที่ขาวโล่งๆ ต่อเนื่องกัน "40 พิกเซล" 
        # (ตารางปกติจะไม่มีทางขาวโล่งยาวขนาดนี้ เพราะติดเส้นแนวตั้ง)
        if empty_streak > 40:
            # สั่งตัดโดยย้อนกลับไป 40 พิกเซล (เพื่อชิดขอบตารางเป๊ะๆ) + เผื่อความหนาเส้น 5 พิกเซล
            bottom_crop = y - 40 + 5
            break # เลิกสแกน! หั่นตรงนี้เลย!
            
    bottom_crop = min(bottom_crop, height)
    img = img.crop((0, 0, width, bottom_crop))
    
    out_bytes = io.BytesIO()
    img.save(out_bytes, format="PNG")
    return out_bytes.getvalue()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (Top-Down Scanner Mode)!"}

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
                mat = fitz.Matrix(3.0, 3.0) 
                pix = page.get_pixmap(matrix=mat)
                
                # เข้าเครื่องสแกน Top-Down
                cropped_png_bytes = trim_top_down_white_space(pix.tobytes("png"))
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, cropped_png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})
    
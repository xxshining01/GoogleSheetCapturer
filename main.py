from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "✅ API is online and ready to convert PDF to ZIP!"}

@app.post("/convert")
async def convert_to_zip(
    file: UploadFile = File(...),
    names: str = Form(...),
    ratios: str = Form(...)  # รับค่าสัดส่วน Vertical/Horizontal จาก App Script
):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        name_list = [n.strip() for n in names.split(",")]
        ratio_list = [float(r.strip()) for r in ratios.split(",")]

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(len(doc)):
                page = doc.load_page(i)

                # ใช้ scale 3x เพื่อความละเอียดสูง
                mat = fitz.Matrix(3.0, 3.0)
                pix = page.get_pixmap(matrix=mat)

                # แปลงเป็น Pillow Image เพื่อครอป
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                # คำนวณ target_height จากสัดส่วนที่ App Script ส่งมา
                # ratio = totalHeight / totalWidth (หน่วย pixel ของ Sheet)
                # img.width คือ Horizontal จริงของภาพ PNG ที่เรนเดอร์แล้ว
                current_ratio = ratio_list[i] if i < len(ratio_list) else ratio_list[-1]
                target_height = int(img.width * current_ratio)

                # ป้องกันกรณี target_height เกินขนาดจริงของภาพ
                target_height = min(target_height, img.height)

                # ครอปจาก (0,0) ถึง (width, target_height)
                img_cropped = img.crop((0, 0, img.width, target_height))

                # บันทึกเป็น PNG
                out_bytes = io.BytesIO()
                img_cropped.save(out_bytes, format="PNG")

                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, out_bytes.getvalue())

        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})
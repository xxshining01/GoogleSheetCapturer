from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz
import zipfile
import io
import base64
import json
import numpy as np
from PIL import Image

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "✅ API Online — Multi-PDF Batch Mode"}

def auto_crop_whitespace(img: Image.Image, padding: int = 4) -> Image.Image:
    arr = np.array(img.convert("RGB"))
    mask = np.any(arr < 250, axis=2)
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any():
        return img
    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    h, w = arr.shape[:2]
    return img.crop((
        max(0, c0 - padding),
        max(0, r0 - padding),
        min(w, c1 + padding + 1),
        min(h, r1 + padding + 1)
    ))

@app.post("/convert")
async def convert_to_zip(
    file: UploadFile = File(...),
    names: str = Form(...),
    ratios: str = Form(default=""),
    scale: float = Form(default=3.0),
    padding: int = Form(default=4),
    output_format: str = Form(default="png")
):
    try:
        raw = await file.read()
        name_list = [n.strip() for n in names.split(",")]
        fmt = output_format.lower()

        zip_buffer = io.BytesIO()

        # ตรวจว่าเป็น JSON array (multi-PDF mode) หรือ PDF เดียว
        if raw[:1] == b'[' or raw[:1] == b'"':
            # Multi-PDF mode: รับ JSON array ของ base64-encoded PDFs
            pdf_list = json.loads(raw.decode('utf-8'))
            pdfs = [base64.b64decode(p) for p in pdf_list]
        else:
            # Single PDF mode (backward compatible): แยกเป็น 1 PDF ต่อ 1 หน้า
            doc_all = fitz.open(stream=raw, filetype="pdf")
            pdfs = []
            for i in range(len(doc_all)):
                page = doc_all.load_page(i)
                writer = fitz.open()
                writer.insert_pdf(doc_all, from_page=i, to_page=i)
                buf = io.BytesIO()
                writer.save(buf)
                pdfs.append(buf.getvalue())

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, pdf_bytes in enumerate(pdfs):
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = doc.load_page(0)  # แต่ละ pdf = 1 หน้า
                mat = fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                img_cropped = auto_crop_whitespace(img, padding=padding)

                out = io.BytesIO()
                if fmt in ("jpg", "jpeg"):
                    img_cropped.convert("RGB").save(out, format="JPEG", quality=95)
                    ext = "jpg"
                else:
                    img_cropped.save(out, format="PNG")
                    ext = "png"

                name = name_list[i] if i < len(name_list) else f"page_{i+1}"
                zf.writestr(f"{name}.{ext}", out.getvalue())

        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
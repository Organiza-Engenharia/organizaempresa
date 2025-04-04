import time  
from flask import Flask, request, jsonify, send_file, render_template
import os
import fitz  # PyMuPDF
import pdfkit
import requests
import pytesseract
from PIL import Image, ImageEnhance
import io
import logging

# =============================================
# CONFIGURAÇÕES DE LOGGING E FLASK
# =============================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

# =============================================
# FUNÇÕES AUXILIARES
# =============================================
def enhance_image(img):
    try:
        img = img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(2.0)
    except Exception as e:
        logger.error(f"Erro no processamento de imagem: {e}")
        return img

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page_num, page in enumerate(doc, 1):
                extracted_text = page.get_text("text")
                if extracted_text.strip():
                    logger.info(f"Página {page_num}: Texto extraído ({len(extracted_text)} caracteres)")
                    text += extracted_text + "\n"
                    continue

                # OCR apenas se Tesseract estiver disponível
                if hasattr(pytesseract, "image_to_string"):
                    logger.info(f"Página {page_num}: Iniciando OCR...")
                    try:
                        pix = page.get_pixmap(dpi=300)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        img = enhance_image(img)

                        ocr_text = pytesseract.image_to_string(
                            img,
                            lang="por+eng",
                            config='--psm 6 --oem 3'
                        )
                        if ocr_text.strip():
                            logger.info(f"OCR Página {page_num} extraiu: {ocr_text[:50]}...")
                            text += ocr_text + "\n"
                        else:
                            logger.warning(f"OCR Página {page_num} não retornou texto")
                    except Exception as ocr_error:
                        logger.warning(f"OCR não disponível: {ocr_error}")
                else:
                    logger.warning("OCR ignorado (Tesseract não disponível no ambiente)")

    except Exception as e:
        logger.error(f"Erro ao processar PDF: {str(e)}")
        raise

    logger.info(f"Texto total extraído: {len(text)} caracteres")
    return text.strip()

def summarize_text(text):
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{
            "role": "user",
            "content": f"""
            Você é um especialista em legislação trabalhista. Resuma este documento detalhadamente:
            {text}
            """
        }],
        "temperature": 0.6,
        "max_tokens": 3000
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Erro na API DeepSeek: {e}")
        return f"Erro ao gerar resumo: {str(e)}"

def create_pdf(summary, output_path, title="Resumo Documento"):
    html = f"""
    <html>
    <head><meta charset="UTF-8"><title>{title}</title>
    <style>
        body {{ font-family: Arial; margin: 20px; line-height: 1.6; }}
        h1 {{ color: #006855; text-align: center; }}
        .content {{ background: #f9f9f9; padding: 15px; }}
    </style>
    </head>
    <body>
        <h1>{title}</h1>
        <div class="content">{summary.replace('\n', '<br>')}</div>
    </body>
    </html>
    """

    try:
        pdfkit.from_string(
            html,
            output_path,
            options={
                'page-size': 'A4',
                'encoding': 'UTF-8',
                'margin-top': '10mm',
                'margin-bottom': '10mm'
            }
            # ⚠️ Comentado pois wkhtmltopdf não está disponível no Render
            # , configuration=pdfkit.configuration(
            #     wkhtmltopdf="/usr/bin/wkhtmltopdf"
            # )
        )
    except Exception as e:
        logger.warning(f"PDF não gerado (ignorado no ambiente Render): {e}")

# =============================================
# ROTAS FLASK
# =============================================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Nome de arquivo inválido"}), 400

        temp_path = "temp.pdf"
        file.save(temp_path)

        text = extract_text_from_pdf(temp_path)
        if not text.strip():
            return jsonify({"error": "Não foi possível extrair texto"}), 400

        summary = summarize_text(text)
        return jsonify({
            "success": True,
            "resumo": summary
        })

    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists("temp.pdf"):
            os.remove("temp.pdf")

@app.route("/mensagem", methods=["POST"])
def processar_mensagem():
    try:
        data = request.get_json()
        user_input = data.get("mensagem", "").strip()

        if not user_input:
            return jsonify({"error": "Mensagem vazia"}), 400

        DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
        DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{
                "role": "user",
                "content": f"""
                Você é um especialista em legislação trabalhista. Responda à pergunta a seguir com precisão e clareza:
                {user_input}
                """
            }],
            "temperature": 0.6,
            "max_tokens": 3000
        }

        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]

        return jsonify({"success": True, "resposta": answer})

    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================
# INICIALIZAÇÃO
# =============================================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

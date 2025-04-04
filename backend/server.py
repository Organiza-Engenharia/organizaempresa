import time  
from flask import Flask, request, jsonify, send_file, render_template
import os
import fitz  # PyMuPDF para leitura de PDFs
import pdfkit  # Para gerar PDF
import requests  # Para chamar a API da DeepSeek
import pytesseract
from PIL import Image, ImageEnhance  # Manipular imagens extraídas do PDF
import io  # Para manipular os bytes da imagem extraída
import logging

# =============================================
# CONFIGURAÇÕES ESSENCIAIS (VERIFIQUE OS CAMINHOS!)
# =============================================
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR"
os.environ["TESSDATA_PREFIX"] = os.path.join(TESSERACT_PATH, "tessdata")
pytesseract.pytesseract.tesseract_cmd = os.path.join(TESSERACT_PATH, "tesseract.exe")

# Verificação de instalação do Tesseract
if not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
    raise RuntimeError("Tesseract não encontrado no caminho especificado!")
if not os.path.exists(os.environ["TESSDATA_PREFIX"]):
    raise RuntimeError(f"Pasta tessdata não encontrada em: {os.environ['TESSDATA_PREFIX']}")

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")


# =============================================
# FUNÇÕES AUXILIARES
# =============================================
def enhance_image(img):
    """Melhora a qualidade da imagem para OCR"""
    try:
        img = img.convert('L')  # Escala de cinza
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
                # Extração direta
                extracted_text = page.get_text("text")
                if extracted_text.strip():
                    logger.info(f"Página {page_num}: Texto extraído ({len(extracted_text)} caracteres)")
                    text += extracted_text + "\n"
                    continue
                
                # Fallback para OCR
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
                        logger.info(f"OCR Página {page_num} extraiu: {ocr_text[:50]}...")  # Mostra início do texto
                        text += ocr_text + "\n"
                    else:
                        logger.warning(f"OCR Página {page_num} não retornou texto")
                        
                except Exception as ocr_error:
                    logger.error(f"Erro no OCR (Página {page_num}): {str(ocr_error)}")
                    raise

    except Exception as e:
        logger.error(f"Erro ao processar PDF: {str(e)}")
        raise

    logger.info(f"Texto total extraído: {len(text)} caracteres")  # Confirmação final
    return text.strip()

def summarize_text(text):
    """Gera resumo usando API DeepSeek"""
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-c09b614705c14f968ae5e8b75c8e7ef4")

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
    """Gera PDF formatado"""
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
            },
            configuration=pdfkit.configuration(
                wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
            )
        )
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        raise

# =============================================
# ROTAS PRINCIPAIS
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

        # Retorna diretamente o resumo no JSON
        return jsonify({
            "success": True,
            "resumo": summary
        })

    except Exception as e:
        logger.error(f"Erro no upload: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route("/download/<filename>")
def download_file(filename):
    try:
        file_path = os.path.join(os.getcwd(), filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        return jsonify({"error": "Arquivo não encontrado"}), 404
    except Exception as e:
        logger.error(f"Erro no download: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/mensagem", methods=["POST"])
def processar_mensagem():
    try:
        data = request.get_json()
        user_input = data.get("mensagem", "").strip()

        if not user_input:
            return jsonify({"error": "Mensagem vazia"}), 400

        DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
        DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-c09b614705c14f968ae5e8b75c8e7ef4")

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
    # Verificação final do Tesseract
    try:
        test_img = Image.new('RGB', (100, 100), color='white')
        pytesseract.image_to_string(test_img, lang='por+eng')
        logger.info("✅ Tesseract configurado corretamente")
    except Exception as e:
        logger.error(f"❌ Falha na verificação do Tesseract: {e}")

    app.run(debug=True, host="0.0.0.0", port=5000)
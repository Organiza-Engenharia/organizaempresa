import pytesseract
from PIL import Image

img = Image.new('RGB', (200, 100), color='white')
print(pytesseract.image_to_string(img, lang='por+eng'))
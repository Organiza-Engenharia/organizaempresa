import smtplib
from email.mime.text import MIMEText

MAILTRAP_HOST = "sandbox.smtp.mailtrap.io"
MAILTRAP_PORT = 587
MAILTRAP_USER = "d7eefb97cac843"
MAILTRAP_PASS = "cbb30a53e9fed0"

msg = MIMEText("Teste de envio de e-mail pelo servidor Flask via Mailtrap")
msg["Subject"] = "Teste Mailtrap"
msg["From"] = "no-reply@organizaengenharia.com.br"
msg["To"] = "fabrinarpaulus@gmail.com"

try:
    server = smtplib.SMTP(MAILTRAP_HOST, MAILTRAP_PORT)
    server.starttls()
    server.login(MAILTRAP_USER, MAILTRAP_PASS)
    server.sendmail(msg["From"], msg["To"], msg.as_string())
    server.quit()
    print("✅ E-mail enviado com sucesso via Mailtrap!")
except Exception as e:
    print(f"❌ Erro ao enviar e-mail via Mailtrap: {e}")

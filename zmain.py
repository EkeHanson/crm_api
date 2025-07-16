import smtplib
import ssl

host = "smtp.gmail.com"
port = 587
username = "ekenehanson@gmail.com"
password = "pduw cpmw dgoq adrp"

try:
    server = smtplib.SMTP(host, port, timeout=10)
    server.set_debuglevel(1)  # Enable debug output
    server.starttls(context=ssl.create_default_context())
    server.login(username, password)
    print("Connection successful!")
    server.quit()
except Exception as e:
    print(f"Connection failed: {str(e)}")
import qrcode
ip="192.168.31.173"
for table in range(1, 8):
    url = f"http://{ip}:5000/menu/{table}"
    img = qrcode.make(url)
    img.save(f"static/qr/table_{table}.png")
print("QR Codes Generated Successfully")

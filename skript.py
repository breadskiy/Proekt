import qrcode

bot_link = "*" # Вместо звездочки необходимо написать адрес сайта

qr = qrcode.QRCode(
    version=2,  
    error_correction=qrcode.constants.ERROR_CORRECT_L,  
    box_size=10,  
    border=4, 
)
qr.add_data(bot_link)
qr.make(fit=True)


img = qr.make_image(fill="black", back_color="white")
img.save("bot_qr.png")

print("QR-код сохранен как bot_qr.png")

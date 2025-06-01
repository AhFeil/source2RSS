import os
import base64
from io import BytesIO

from PIL import Image, ImageDraw


def save_qrcode(qr_code, path) -> None:  # type: ignore
    """parse base64 encode qrcode image and show it"""
    if "," in qr_code:
        qr_code = qr_code.split(",")[1]
    qr_code = base64.b64decode(qr_code)
    image = Image.open(BytesIO(qr_code))

    # Add a square border around the QR code and display it within the border to improve scanning accuracy.
    width, height = image.size
    new_image = Image.new('RGB', (width + 20, height + 20), color=(255, 255, 255))
    new_image.paste(image, (10, 10))
    draw = ImageDraw.Draw(new_image)
    draw.rectangle((0, 0, width + 19, height + 19), outline=(0, 0, 0), width=1)
    filename = os.path.join(path, "qr_code.png")
    with open(filename, 'wb') as f:
        new_image.save(f, 'PNG')

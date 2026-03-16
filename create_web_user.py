#!/usr/bin/env python3
"""Create web app user. Run once to set up login/password and 2FA."""
import getpass
import sys

try:
    import pyotp
    import qrcode
    from io import BytesIO
except ImportError:
    print("Install: pip install pyotp qrcode")
    sys.exit(1)

from werkzeug.security import generate_password_hash
from db.models import User, get_session


def main():
    session = get_session()
    try:
        existing = session.query(User).first()
        if existing:
            print("User already exists. Use DB to reset or create another user.")
            return 1

        username = input("Username: ").strip()
        if not username:
            print("Username required")
            return 1
        if session.query(User).filter(User.username == username).first():
            print("Username already taken")
            return 1

        password = getpass.getpass("Password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters")
            return 1

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=username, issuer_name="MonelANAL")

        user = User(
            username=username,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            totp_secret=secret,
            totp_verified=True,
        )
        session.add(user)
        session.commit()

        print("\nUser created. Add 2FA to your authenticator app:")
        print(f"Secret (manual entry): {secret}")
        print("\nOr scan QR code (saved to qr_2fa.png):")
        img = qrcode.make(provisioning_uri)
        img.save("qr_2fa.png")
        print("  File: qr_2fa.png")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main() or 0)

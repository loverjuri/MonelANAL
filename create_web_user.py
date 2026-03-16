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


def _link_telegram():
    """Link existing user to Telegram (CHAT_ID). Run: python create_web_user.py --link-telegram"""
    try:
        from config import get_chat_id
        chat_id = get_chat_id()
        if not chat_id:
            print("CHAT_ID not set. Set env or Config.ChatID.")
            return 1
        session = get_session()
        try:
            user = session.query(User).first()
            if not user:
                print("No user exists. Create one first.")
                return 1
            user.telegram_user_id = str(chat_id).strip()
            session.commit()
            print(f"Linked user {user.username} to Telegram (id={chat_id})")
            return 0
        finally:
            session.close()
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main():
    if "--link-telegram" in sys.argv:
        return _link_telegram()
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

        telegram_user_id = None
        try:
            from config import get_chat_id
            chat_id = get_chat_id()
            if chat_id:
                link = input("Link with Telegram (CHAT_ID)? [y/n]: ").strip().lower()
                if link == "y" or link == "yes":
                    telegram_user_id = str(chat_id).strip()
                    print(f"Will link to Telegram user id: {telegram_user_id}")
        except Exception:
            pass

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=username, issuer_name="MonelANAL")

        user = User(
            username=username,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
            totp_secret=secret,
            totp_verified=True,
            telegram_user_id=telegram_user_id,
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

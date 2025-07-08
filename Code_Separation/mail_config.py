from dotenv import load_dotenv
import os
import getpass

load_dotenv()  # Load from .env

EMAIL_USER = os.getenv("EMAIL_USER") or input("Enter your email address: ")
EMAIL_PASS = os.getenv("EMAIL_PASS") or getpass.getpass("Enter your email password or app password: ")

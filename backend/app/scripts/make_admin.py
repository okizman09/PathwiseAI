import argparse
import sys

from app.db import SessionLocal
from app.models.profile import Profile


def make_admin(email: str):
    db = SessionLocal()
    try:
        profile = db.query(Profile).filter(Profile.email == email).first()
        if not profile:
            print(f"Error: No profile found for email '{email}'.")
            print("The user must sign in via Supabase at least once before you can make them an admin.")
            sys.exit(1)

        profile.role = "admin"
        db.commit()
        print(f"Success: {email} is now an admin.")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make an existing user an admin.")
    parser.add_argument("email", type=str, help="The email address of the user")
    args = parser.parse_args()
    make_admin(args.email)

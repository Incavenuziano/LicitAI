import argparse
from sqlalchemy.orm import Session

from .database import SessionLocal
from . import crud, models


def reset_or_create_user(db: Session, email: str, password: str, nickname: str | None = None) -> models.User:
    user = crud.get_user_by_email(db, email=email)
    hashed = crud.get_password_hash(password)
    if user:
        user.hashed_password = hashed
        if nickname is not None:
            user.nickname = nickname
        db.commit()
        db.refresh(user)
        print(f"Senha atualizada para o usuário: {email}")
        return user
    else:
        user = models.User(email=email, hashed_password=hashed, nickname=nickname)
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Usuário criado: {email}")
        return user


def main():
    parser = argparse.ArgumentParser(description="Resetar ou criar usuário (dev tool)")
    parser.add_argument("--email", required=True, help="Email do usuário")
    parser.add_argument("--password", required=True, help="Nova senha")
    parser.add_argument("--nickname", required=False, default=None, help="Nickname opcional")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        reset_or_create_user(db, email=args.email, password=args.password, nickname=args.nickname)
    finally:
        db.close()


if __name__ == "__main__":
    main()


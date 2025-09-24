from typing import Optional
from sqlalchemy.orm import Session

from src import crud, models
from src.database import SessionLocal
from src.crud import pwd_context


def reset_or_create_user(
    db: Session,
    email: str,
    password: str,
    nickname: Optional[str] = None,
) -> models.User:
    email = (email or "").strip().lower()
    user = crud.get_user_by_email(db, email=email)

    if user:
        user.hashed_password = pwd_context.hash(password)
        if nickname is not None:
            user.nickname = nickname
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    user = crud.create_user(
        db,
        models.schemas.UserCreate(
            email=email,
            password=password,
            nickname=nickname,
        ),
    )
    return user


def main(email: str, password: str, nickname: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        user = reset_or_create_user(db, email, password, nickname)
        print(f"Usuário atualizado/criado: {user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Resetar ou criar usuário.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--nickname")
    args = parser.parse_args()

    main(args.email, args.password, args.nickname)

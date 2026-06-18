from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import UserProfileUpdateRequest, UserRegisterRequest


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    statement = select(User).where(User.email == normalize_email(email))
    return db.scalar(statement)


def create_user(db: Session, request: UserRegisterRequest) -> User:
    user = User(
        email=normalize_email(request.email),
        display_name=request.display_name.strip(),
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_profile(
    db: Session,
    user: User,
    request: UserProfileUpdateRequest,
) -> User:
    user.display_name = request.display_name.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def normalize_email(email: str) -> str:
    return email.strip().lower()

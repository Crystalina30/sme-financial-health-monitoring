"""User registration and authentication."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Look up a user by email address, case-insensitively."""
    return db.execute(
        select(User).where(User.email == email.lower().strip())
    ).scalar_one_or_none()


def register_user(db: Session, email: str, full_name: str, password: str) -> User:
    """Create a new user. Raises ValueError when the email is already taken."""
    normalised_email = email.lower().strip()
    if get_user_by_email(db, normalised_email) is not None:
        raise ValueError("An account with this email address already exists.")

    user = User(
        email=normalised_email,
        full_name=full_name.strip(),
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user when the credentials are correct, otherwise None."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_access_token(user: User) -> str:
    """Create a signed access token for an authenticated user."""
    return create_access_token(subject=str(user.id))

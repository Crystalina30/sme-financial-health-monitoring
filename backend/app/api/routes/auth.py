"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.authentication_service import (
    authenticate_user,
    issue_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user account",
)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> User:
    try:
        return register_user(
            db, email=payload.email, full_name=payload.full_name, password=payload.password
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.post("/login", response_model=TokenResponse, summary="Obtain an access token")
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        # One message for both unknown email and wrong password, so the API
        # does not reveal which accounts exist.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email address or password.",
        )
    return TokenResponse(
        access_token=issue_access_token(user),
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.get("/me", response_model=UserResponse, summary="Current account details")
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/logout", summary="Log out")
def logout(current_user: User = Depends(get_current_user)) -> dict:
    """Log the user out.

    Access tokens are stateless and self-expiring, so logging out means the
    client discarding its token; the server keeps no session to destroy. This
    endpoint exists so the frontend has one place to call, and so that this
    design decision is documented rather than implied. Revoking a token before
    it expires would require a server-side deny list, which FYP1 does not
    implement.
    """
    return {
        "detail": "Logged out. Discard the access token on the client.",
        "user_id": current_user.id,
    }

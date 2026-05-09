from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    normalize_email,
    verify_password,
)
from app.database import db
from app.models import TokenResponse, UserCreate, UserLogin, UserPublic

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate):
    email = normalize_email(payload.email)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    if db.get_user_auth_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    password_hash = hash_password(payload.password)
    return db.create_user(email=email, password_hash=password_hash, language=payload.language)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin):
    email = normalize_email(payload.email)
    user_auth = db.get_user_auth_by_email(email)

    if not user_auth or not verify_password(payload.password, user_auth["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials, try again")

    user = UserPublic(
        id=user_auth["id"],
        email=user_auth["email"],
        language=user_auth.get("language", "en"),
        created_at=user_auth["created_at"],
        updated_at=user_auth["updated_at"],
    )
    token, _, _ = create_access_token(user)

    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
    )


@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: UserPublic = Depends(get_current_user),
):
    payload = decode_access_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")

    if not jti or not exp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token payload")

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
    db.revoke_token(jti=jti, user_id=current_user.id, expires_at=expires_at)

    return {"status": "signed_out"}


@router.get("/me", response_model=UserPublic)
async def me(current_user: UserPublic = Depends(get_current_user)):
    return current_user

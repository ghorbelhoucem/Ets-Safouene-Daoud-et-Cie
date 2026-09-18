from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import AuditEvent, ItemCategory, User, UserRole

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)
ROLE_KEY_TO_ENUM = {
    "maintenance": UserRole.maintenance,
    "management": UserRole.management,
}

def hash_secret(secret: str) -> str:
    return pwd.hash(secret)

def verify_secret(secret: str, secret_hash: str | None) -> bool:
    return bool(secret_hash) and pwd.verify(secret, secret_hash)

def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "name": user.name, "role": user.role.value,
                       "iat": now, "exp": now + timedelta(minutes=settings.jwt_expire_minutes)},
                      settings.jwt_secret, algorithm="HS256")

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Connexion requise")
    try:
        data = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        user_id = UUID(data["sub"])
        user = db.get(User, user_id)
    except (JWTError, ValueError, TypeError):
        user = None
    if user is None or not user.is_active:
        raise HTTPException(401, "Session invalide ou expirée")
    return user

def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Permissions insuffisantes")
        return user
    return dependency

require_manager = require_roles(UserRole.management)
require_report_access = require_roles(UserRole.management)
require_restock_access = require_roles(UserRole.management)

def can_restock_category(user: User, category: ItemCategory) -> bool:
    return user.role == UserRole.management and category != ItemCategory.sops

def audit(db: Session, event_type: str, actor: str | None = None, detail: str | None = None):
    db.add(AuditEvent(event_type=event_type, actor=actor, detail=detail))

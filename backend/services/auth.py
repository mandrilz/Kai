"""
Сервис аутентификации: генерация и валидация JWT, работа с magic-link токенами.
"""
import jwt
import os
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional
from models import MagicLinkToken, User, get_session, select
from sqlmodel import Session


# Секретный ключ для JWT (в продакшене должен быть в env)
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 дней


def generate_jwt(user_id: str) -> str:
    """Генерирует JWT токен для пользователя."""
    payload = {
        "user_id": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> Optional[str]:
    """
    Проверяет JWT токен и возвращает user_id.
    Возвращает None если токен невалиден.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def create_magic_link_token(email: str, session: Session) -> str:
    """
    Создает одноразовый токен для magic-link.
    Возвращает токен (UUID string).
    """
    try:
        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=15)  # TTL 15 минут
        
        # Проверяем, есть ли пользователь с таким email
        user = session.exec(select(User).where(User.email == email)).first()
        
        magic_token = MagicLinkToken(
            token=token,
            email=email,
            user_id=user.id if user else None,
            expires_at=expires_at,
        )
        session.add(magic_token)
        session.commit()
        session.refresh(magic_token)
        
        return token
    except Exception as e:
        print(f"[AUTH] Ошибка при создании magic-link токена для {email}: {type(e).__name__}: {str(e)}")
        session.rollback()
        raise


def verify_magic_link_token(token: str, session: Session) -> Optional[User]:
    """
    Проверяет magic-link токен и возвращает/создает пользователя.
    Возвращает None если токен невалиден или истек.
    """
    try:
        print(f"[AUTH] Поиск токена в БД: {token[:20]}...")
        magic_token = session.exec(
            select(MagicLinkToken).where(MagicLinkToken.token == token)
        ).first()
        
        if not magic_token:
            print(f"[AUTH] Токен не найден в БД: {token[:20]}...")
            return None
        
        print(f"[AUTH] Токен найден: email={magic_token.email}, expires_at={magic_token.expires_at}, used_at={magic_token.used_at}")
        
        # Проверяем срок действия
        now = datetime.utcnow()
        if now > magic_token.expires_at:
            print(f"[AUTH] Токен истек: expires_at={magic_token.expires_at}, now={now}")
            return None
        
        # Проверяем, не использован ли уже
        if magic_token.used_at:
            print(f"[AUTH] Токен уже использован: used_at={magic_token.used_at}")
            return None
        
        # Помечаем токен как использованный
        magic_token.used_at = datetime.utcnow()
        session.add(magic_token)
        session.flush()  # Применяем изменения, но не коммитим еще
        
        # Находим или создаем пользователя
        if magic_token.user_id:
            print(f"[AUTH] Поиск существующего пользователя: user_id={magic_token.user_id}")
            user = session.get(User, magic_token.user_id)
            if not user:
                print(f"[AUTH] Пользователь с user_id={magic_token.user_id} не найден, создаем нового")
                user = User(email=magic_token.email)
                session.add(user)
                session.flush()
                session.refresh(user)
        else:
            # Создаем нового пользователя
            print(f"[AUTH] Создание нового пользователя: email={magic_token.email}")
            user = User(email=magic_token.email)
            session.add(user)
            session.flush()
            session.refresh(user)
            
            # Обновляем токен с user_id
            magic_token.user_id = user.id
            session.add(magic_token)
        
        session.commit()
        print(f"[AUTH] Пользователь успешно найден/создан: id={user.id}, email={user.email}")
        return user
    except Exception as e:
        print(f"[AUTH] Ошибка при проверке токена: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[AUTH] Traceback:\n{traceback.format_exc()}")
        session.rollback()
        raise

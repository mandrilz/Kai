"""
API endpoints для аутентификации (magic-link).
"""
from fastapi import APIRouter, HTTPException, status, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime
from models import get_session
from services.auth import create_magic_link_token, verify_magic_link_token, generate_jwt


router = APIRouter(prefix="/auth", tags=["auth"])


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    message: str


class VerifyResponse(BaseModel):
    token: str  # JWT token
    user_id: str


def send_magic_link_email(email: str, token: str) -> bool:
    """
    Отправляет письмо с magic-link.
    Использует SMTP из переменных окружения.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    if not smtp_user or not smtp_pass:
        # В режиме разработки просто логируем
        print(f"[DEV] Magic-link для {email}: {frontend_url}/auth/callback?token={token}")
        return True
    
    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = email
        msg["Subject"] = "Вход в K.ai (Кометтик)"
        
        link = f"{frontend_url}/auth/callback?token={token}"
        body = f"""
        Здравствуйте!
        
        Вы запросили вход в систему K.ai (Кометтик).
        
        Перейдите по ссылке для входа:
        {link}
        
        Ссылка действительна 15 минут.
        
        Если вы не запрашивали вход, проигнорируйте это письмо.
        """
        
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        # Правильная обработка портов 465 (SMTPS) и 587 (STARTTLS)
        if smtp_port == 465:
            # Порт 465 использует SSL/TLS из коробки (SMTPS)
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            # Порт 587 использует STARTTLS (обычный SMTP)
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"[AUTH] Ошибка отправки email на {smtp_host}:{smtp_port}: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"[AUTH] Traceback:\n{traceback.format_exc()}")
        return False


@router.post("/magic-link", response_model=MagicLinkResponse)
async def request_magic_link(request: MagicLinkRequest):
    """
    Генерирует magic-link токен и отправляет письмо пользователю.
    """
    import traceback
    
    session = None
    try:
        print(f"[AUTH] Запрос magic-link для email: {request.email}")
        session = get_session()
        token = create_magic_link_token(request.email, session)
        print(f"[AUTH] Токен создан для {request.email}: {token[:20]}...")
        
        # Отправляем письмо
        email_sent = send_magic_link_email(request.email, token)
        
        if not email_sent:
            print(f"[AUTH] ОШИБКА: Не удалось отправить письмо для {request.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось отправить письмо",
            )
        
        print(f"[AUTH] Magic-link успешно отправлен для {request.email}")
        return MagicLinkResponse(
            message="Ссылка для входа отправлена на ваш email. Проверьте почту."
        )
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[AUTH] КРИТИЧЕСКАЯ ОШИБКА при создании magic-link для {request.email}:")
        print(f"[AUTH] Тип ошибки: {type(e).__name__}")
        print(f"[AUTH] Сообщение: {str(e)}")
        print(f"[AUTH] Traceback:\n{error_trace}")
        
        # Логируем в файл
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] AUTH ERROR: {type(e).__name__}: {str(e)}\n")
                f.write(f"Traceback: {error_trace}\n")
        except:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании magic-link: {str(e)}",
        )
    finally:
        if session:
            session.close()


@router.get("/verify", response_model=VerifyResponse)
async def verify_magic_link(token: str, response: Response):
    """
    Проверяет magic-link токен и возвращает JWT.
    Устанавливает JWT в cookie.
    """
    import traceback
    
    session = None
    try:
        print(f"[AUTH] Проверка токена: {token[:20]}...")
        session = get_session()
        user = verify_magic_link_token(token, session)
        
        if not user:
            print(f"[AUTH] Токен невалиден или истек: {token[:20]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный или истекший токен",
            )
        
        print(f"[AUTH] Токен валиден, пользователь найден: {user.email} (id: {user.id})")
        
        # Генерируем JWT
        jwt_token = generate_jwt(str(user.id))
        print(f"[AUTH] JWT сгенерирован для user_id: {user.id}")
        
        # Устанавливаем cookie
        is_production = os.getenv("ENVIRONMENT") == "production"
        response.set_cookie(
            key="auth_token",
            value=jwt_token,
            httponly=True,
            secure=is_production,  # HTTPS только в продакшене
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 дней
            path="/",  # Явно указываем путь
        )
        
        print(f"[AUTH] Cookie установлен (secure={is_production})")
        
        return VerifyResponse(token=jwt_token, user_id=str(user.id))
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[AUTH] КРИТИЧЕСКАЯ ОШИБКА при проверке токена:")
        print(f"[AUTH] Тип ошибки: {type(e).__name__}")
        print(f"[AUTH] Сообщение: {str(e)}")
        print(f"[AUTH] Traceback:\n{error_trace}")
        
        # Логируем в файл
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] AUTH VERIFY ERROR: {type(e).__name__}: {str(e)}\n")
                f.write(f"Traceback: {error_trace}\n")
        except:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при проверке токена: {str(e)}",
        )
    finally:
        if session:
            session.close()

"""
Middleware для проверки JWT аутентификации.
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from services.auth import verify_jwt


security = HTTPBearer(auto_error=False)


async def get_current_user_id(request: Request) -> Optional[str]:
    """
    Извлекает user_id из JWT токена (из cookie или Authorization header).
    Устанавливает request.state.user_id.
    Возвращает user_id или None если не авторизован.
    """
    user_id = None
    
    # Пробуем получить из cookie
    token = request.cookies.get("auth_token")
    
    # Если нет в cookie, пробуем из Authorization header
    if not token:
        authorization: Optional[HTTPAuthorizationCredentials] = await security(request)
        if authorization:
            token = authorization.credentials
    
    if token:
        user_id = verify_jwt(token)
    
    request.state.user_id = user_id
    return user_id


async def require_auth(request: Request) -> str:
    """
    Требует аутентификации. Вызывает HTTPException 401 если пользователь не авторизован.
    Возвращает user_id.
    """
    user_id = await get_current_user_id(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация",
        )
    return user_id

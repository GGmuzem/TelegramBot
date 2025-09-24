"""
Web App маршруты для интерфейса платежей
"""
import json
import logging
from datetime import datetime
from aiohttp import web
from aiohttp.web import RouteTableDef

from src.shared.config import settings, PACKAGES
from src.payment.providers.yookassa import YooKassaProvider
from src.database.crud import UserCRUD, PaymentCRUD

logger = logging.getLogger(__name__)
routes = RouteTableDef()

# Сервисы
yookassa_provider = YooKassaProvider()
user_crud = UserCRUD()
payment_crud = PaymentCRUD()


def setup_webapp_routes(app: web.Application):
    """Настройка маршрутов для Web App"""
    app.router.add_routes(routes)


@routes.get('/webapp/payment/{package}')
async def payment_webapp(request: web.Request):
    """Главная страница Web App для оплаты"""
    package = request.match_info['package']
    
    if package not in PACKAGES:
        raise web.HTTPNotFound(text="Package not found")
    
    package_info = PACKAGES[package]
    
    # HTML страница для оплаты
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Оплата - {package_info['name']}</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--tg-theme-bg-color, #ffffff);
            color: var(--tg-theme-text-color, #333333);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 400px;
            margin: 0 auto;
        }}
        
        .package-card {{
            background: var(--tg-theme-secondary-bg-color, #f8f9fa);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }}
        
        .package-title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 8px;
            color: var(--tg-theme-text-color, #333);
        }}
        
        .package-price {{
            font-size: 32px;
            font-weight: bold;
            color: var(--tg-theme-button-color, #007AFF);
            margin-bottom: 16px;
        }}
        
        .package-description {{
            font-size: 16px;
            color: var(--tg-theme-hint-color, #666);
            margin-bottom: 20px;
            line-height: 1.4;
        }}
        
        .features {{
            list-style: none;
            margin-bottom: 24px;
        }}
        
        .features li {{
            padding: 8px 0;
            display: flex;
            align-items: center;
            font-size: 14px;
        }}
        
        .features li::before {{
            content: "✅";
            margin-right: 12px;
        }}
        
        .payment-methods {{
            display: grid;
            gap: 12px;
        }}
        
        .payment-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            color: white;
        }}
        
        .payment-btn:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }}
        
        .payment-btn.card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        
        .payment-btn.sbp {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        
        .payment-btn.sber {{
            background: linear-gradient(135deg, #21D190 0%, #128C7E 100%);
        }}
        
        .payment-btn.yoomoney {{
            background: linear-gradient(135deg, #8B5CF6 0%, #A855F7 100%);
        }}
        
        .loading {{
            display: none;
            text-align: center;
            padding: 40px;
        }}
        
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--tg-theme-button-color, #007AFF);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        .security-info {{
            background: var(--tg-theme-secondary-bg-color, #f8f9fa);
            border-radius: 12px;
            padding: 16px;
            margin-top: 20px;
            font-size: 12px;
            color: var(--tg-theme-hint-color, #666);
            text-align: center;
        }}
        
        .error {{
            background: #fee;
            border: 1px solid #fcc;
            color: #c00;
            padding: 16px;
            border-radius: 12px;
            margin: 16px 0;
            display: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="package-card">
            <h1 class="package-title">{package_info['name']}</h1>
            <div class="package-price">{package_info['price']}₽</div>
            <p class="package-description">{package_info['description']}</p>
            
            <ul class="features">
                <li>{package_info['images']} изображений для генерации</li>
                <li>Высокое качество RTX 5080</li>
                <li>Поддержка всех стилей</li>
                {"<li>Приоритетная очередь</li>" if package in ['premium', 'pro'] else ""}
                {"<li>Без ограничений по времени</li>" if package == 'pro' else ""}
                <li>Фискальный чек по 54-ФЗ</li>
            </ul>
        </div>
        
        <div id="payment-form">
            <div class="payment-methods">
                <button class="payment-btn card" onclick="startPayment('card')">
                    💳 Банковская карта
                </button>
                <button class="payment-btn sbp" onclick="startPayment('sbp')">
                    📱 СБП - Быстрые платежи
                </button>
                <button class="payment-btn sber" onclick="startPayment('sber')">
                    🟢 SberPay
                </button>
                <button class="payment-btn yoomoney" onclick="startPayment('yoomoney')">
                    🟡 ЮMoney
                </button>
            </div>
        </div>
        
        <div id="loading" class="loading">
            <div class="spinner"></div>
            <p>Подготавливаем платеж...</p>
        </div>
        
        <div id="error" class="error">
            <strong>Ошибка:</strong>
            <span id="error-text"></span>
        </div>
        
        <div class="security-info">
            🔒 <strong>Безопасная оплата</strong><br>
            Все платежи защищены по стандарту PCI DSS Level 1<br>
            Данные карт шифруются и не сохраняются
        </div>
    </div>

    <script>
        // Инициализация Telegram WebApp
        let tg = window.Telegram?.WebApp;
        if (tg) {{
            tg.ready();
            tg.expand();
        }}
        
        const package = '{package}';
        
        function showLoading() {{
            document.getElementById('payment-form').style.display = 'none';
            document.getElementById('loading').style.display = 'block';
        }}
        
        function hideLoading() {{
            document.getElementById('payment-form').style.display = 'block';
            document.getElementById('loading').style.display = 'none';
        }}
        
        function showError(message) {{
            const errorDiv = document.getElementById('error');
            const errorText = document.getElementById('error-text');
            errorText.textContent = message;
            errorDiv.style.display = 'block';
            hideLoading();
        }}
        
        async function startPayment(method) {{
            showLoading();
            
            try {{
                // Получаем данные пользователя из Telegram
                const userInfo = tg?.initDataUnsafe?.user || {{}};
                
                // Создаем платеж
                const response = await fetch('/api/payment/create', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-Telegram-Init-Data': tg?.initData || ''
                    }},
                    body: JSON.stringify({{
                        package: package,
                        method: method,
                        user_info: userInfo,
                        return_url: window.location.href
                    }})
                }});
                
                const result = await response.json();
                
                if (response.ok && result.success) {{
                    // Перенаправляем на страницу оплаты
                    if (result.payment_url) {{
                        if (tg) {{
                            tg.openLink(result.payment_url);
                        }} else {{
                            window.open(result.payment_url, '_blank');
                        }}
                    }}
                }} else {{
                    showError(result.error || 'Не удалось создать платеж');
                }}
                
            }} catch (error) {{
                console.error('Payment error:', error);
                showError('Произошла ошибка при создании платежа');
            }}
        }}
        
        // Обработка закрытия WebApp
        if (tg) {{
            tg.onEvent('webAppClose', function() {{
                // Уведомляем бота о закрытии WebApp
                fetch('/api/webapp/close', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-Telegram-Init-Data': tg.initData
                    }},
                    body: JSON.stringify({{ package: package }})
                }}).catch(console.error);
            }});
        }}
    </script>
</body>
</html>
"""
    
    return web.Response(text=html_content, content_type='text/html')


@routes.post('/api/payment/create')
async def create_payment_api(request: web.Request):
    """API создания платежа"""
    try:
        data = await request.json()
        package = data.get('package')
        method = data.get('method')
        user_info = data.get('user_info', {})
        return_url = data.get('return_url')
        
        # Валидация
        if package not in PACKAGES:
            return web.json_response({
                'success': False,
                'error': 'Неизвестный пакет'
            }, status=400)
        
        # Получаем или создаем пользователя
        user_id = user_info.get('id')
        if not user_id:
            return web.json_response({
                'success': False,
                'error': 'Не удалось определить пользователя'
            }, status=400)
        
        user = await user_crud.get_or_create_user(
            telegram_id=user_id,
            username=user_info.get('username'),
            first_name=user_info.get('first_name', 'Unknown'),
            last_name=user_info.get('last_name'),
            language_code=user_info.get('language_code', 'ru')
        )
        
        # Создаем платеж
        payment_result = await yookassa_provider.create_payment(
            user_id=user_id,
            package=package,
            return_url=return_url
        )
        
        return web.json_response({
            'success': True,
            'payment_id': payment_result['payment_id'],
            'payment_url': payment_result['confirmation_url'],
            'amount': payment_result['amount']
        })
        
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return web.json_response({
            'success': False,
            'error': 'Внутренняя ошибка сервера'
        }, status=500)


@routes.get('/webapp/success')
async def payment_success_webapp(request: web.Request):
    """Страница успешной оплаты"""
    payment_id = request.query.get('payment_id', 'unknown')
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Оплата успешна!</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--tg-theme-bg-color, #ffffff);
            color: var(--tg-theme-text-color, #333333);
            padding: 20px;
            text-align: center;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .success-container {{
            max-width: 400px;
            background: var(--tg-theme-secondary-bg-color, #f8f9fa);
            border-radius: 20px;
            padding: 40px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        
        .success-icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}
        
        .success-title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 16px;
            color: #22c55e;
        }}
        
        .success-message {{
            font-size: 16px;
            color: var(--tg-theme-hint-color, #666);
            line-height: 1.5;
            margin-bottom: 30px;
        }}
        
        .payment-info {{
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        
        .close-btn {{
            background: var(--tg-theme-button-color, #007AFF);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 16px 32px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .close-btn:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(0,123,255,0.3);
        }}
    </style>
</head>
<body>
    <div class="success-container">
        <div class="success-icon">✅</div>
        <h1 class="success-title">Оплата успешна!</h1>
        <p class="success-message">
            Ваш платеж был успешно обработан.<br>
            Изображения добавлены на баланс.<br>
            Фискальный чек отправлен на email.
        </p>
        <div class="payment-info">
            <small>ID платежа: {payment_id}</small>
        </div>
        <button class="close-btn" onclick="closeWebApp()">
            Вернуться в бот
        </button>
    </div>

    <script>
        let tg = window.Telegram?.WebApp;
        if (tg) {{
            tg.ready();
            tg.expand();
        }}
        
        function closeWebApp() {{
            if (tg) {{
                tg.close();
            }} else {{
                window.close();
            }}
        }}
        
        // Автоматически закрыть через 10 секунд
        setTimeout(closeWebApp, 10000);
    </script>
</body>
</html>
"""
    
    return web.Response(text=html_content, content_type='text/html')


@routes.post('/api/webapp/close')
async def webapp_close_api(request: web.Request):
    """API уведомления о закрытии WebApp"""
    try:
        data = await request.json()
        logger.info(f"WebApp closed for package: {data.get('package')}")
        return web.json_response({'success': True})
    except Exception as e:
        logger.error(f"WebApp close error: {e}")
        return web.json_response({'success': False}, status=500)


@routes.get('/webapp/error')
async def payment_error_webapp(request: web.Request):
    """Страница ошибки оплаты"""
    error_message = request.query.get('error', 'Неизвестная ошибка')
    
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ошибка оплаты</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--tg-theme-bg-color, #ffffff);
            color: var(--tg-theme-text-color, #333333);
            padding: 20px;
            text-align: center;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .error-container {{
            max-width: 400px;
            background: var(--tg-theme-secondary-bg-color, #f8f9fa);
            border-radius: 20px;
            padding: 40px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        
        .error-icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}
        
        .error-title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 16px;
            color: #ef4444;
        }}
        
        .error-message {{
            font-size: 16px;
            color: var(--tg-theme-hint-color, #666);
            line-height: 1.5;
            margin-bottom: 30px;
        }}
        
        .retry-btn {{
            background: var(--tg-theme-button-color, #007AFF);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 16px 32px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            margin: 8px;
            transition: all 0.2s ease;
        }}
        
        .close-btn {{
            background: #6b7280;
            color: white;
            border: none;
            border-radius: 12px;
            padding: 16px 32px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            margin: 8px;
            transition: all 0.2s ease;
        }}
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-icon">❌</div>
        <h1 class="error-title">Ошибка оплаты</h1>
        <p class="error-message">
            {error_message}<br><br>
            Средства не были списаны.<br>
            Попробуйте еще раз или выберите другой способ оплаты.
        </p>
        <button class="retry-btn" onclick="goBack()">
            Попробовать снова
        </button>
        <button class="close-btn" onclick="closeWebApp()">
            Вернуться в бот
        </button>
    </div>

    <script>
        let tg = window.Telegram?.WebApp;
        if (tg) {{
            tg.ready();
            tg.expand();
        }}
        
        function goBack() {{
            window.history.back();
        }}
        
        function closeWebApp() {{
            if (tg) {{
                tg.close();
            }} else {{
                window.close();
            }}
        }}
    </script>
</body>
</html>
"""
    
    return web.Response(text=html_content, content_type='text/html')
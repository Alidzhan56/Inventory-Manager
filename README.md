# WarePulse – Система за склад и транзакции

WarePulse е уеб приложение за управление на складови наличности и транзакции (покупки/продажби),
с поддръжка на няколко склада, партньори (клиенти/доставчици), роли и табло с графики.

## Основни функции
- Каталог продукти + наличност по склад
- Покупки и продажби с много редове (multi-line транзакции)
- Автоматични движения на наличността (stock movements)
- Партньори: клиенти / доставчици
- Роли и права: Admin/Owner, Warehouse Manager, Sales Agent, Developer
- История на входовете: време, IP, държава (по IP), user-agent
- Dashboard с показатели и графики
- Многоезичност: BG / EN

## Технологии
- Python + Flask
- SQLAlchemy
- Flask-Migrate (миграции)
- Bootstrap 5 (UI)

## Структура на проекта (накратко)
- `app.py` – входна точка
- `inventory/` – основен пакет на приложението
- `inventory/models.py` (или `inventory/models/`) – модели и база данни
- `inventory/templates/` – HTML шаблони
- `inventory/static/` – CSS / JS / изображения
- `instance/` – локални настройки/SQLite база (ако се използва)

## Демонстрационни акаунти
Developer (за тестове):
- DEV_EMAIL=dev@example.com
- DEV_USERNAME=dev
- DEV_PASSWORD=12345678

Admin/Owner
- username= ivan
- password= Owner!123A

Warehouse manager
- username=petar
- password= Manager!123A

Sales Agent
- username= maria
- password= Sales!123A

## Стартиране локално (Windows)
 Създай и активирай виртуална среда:
```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1

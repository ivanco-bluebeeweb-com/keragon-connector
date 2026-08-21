# Keragon Connector — Connector Discovery

**Дата discovery:** 2026-08-21
**Статус:** Ярусы 1-2 пройдены (свежий поиск по официальной документации
2026-08-21: docs.keragon.com, help.keragon.com, keragon.com/pricing,
keragon.com/mcp, keragon.com/brand). Ярус 3 заполнен. Объём релиза выбран
по прямому правилу пользователя ("делай в полном максимуме со всеми
возможными функциями и с их стороны и с нашей") — отдельного
подтверждения объёма не требуется, но архитектурное ограничение ниже
обязательно к прочтению перед Фазой 3.

---

## 1. Целевой сервис и источники

**Keragon** — специализированный HIPAA-compliant iPaaS (workflow
automation) для здравоохранения: ~300+ встроенных коннекторов к
EHR/CRM/scheduling/billing системам (Cerbo, Athena Health, IntakeQ,
OpenEMR, Healthie, Spruce Health, DrChrono, Acuity и т.д.), BAA, SOC 2
Type II. Позиционируется как "the HIPAA-compliant Zapier/Make
alternative" для healthcare-команд.

Источники (прочитаны 2026-08-21):
- `docs.keragon.com` — документация построения СОБСТВЕННОГО коннектора
  ВНУТРИ каталога Keragon (их CLI/SDK, `@keragon/connector-sdk` на npm).
- `help.keragon.com/hc/en-us/categories/18543073677074-Connectors` —
  Connectors help category.
- `help.keragon.com/hc/en-us/articles/*-Using-the-HTTP-Webhook-Trigger`,
  `*-Configuring-and-Testing-Workflow-Triggers`,
  `*-How-to-use-the-HTTP-Client-action-to-make-custom-API-requests`,
  `*-Introduction-to-Workflow-Actions` — trigger/action model.
- `keragon.com/mcp`, `help.keragon.com/.../Introducing-Keragon-MCP`,
  `.../Keragon-MCP-HIPAA-Compliance` — Keragon's own MCP server (для
  ChatGPT/Claude/voice-агентов, читает/пишет в системы ВНУТРИ Keragon).
- `keragon.com/pricing` — Starter/Professional/Scale Up/Enterprise tiers,
  run-based (1 run = 1 execution опубликованного workflow) + credits для
  AI-агентов. Точные цифры не публикуются на странице (JS-рендер,
  "Contact sales" для деталей) — не критично для нашего собственного
  прайсинга ниже (см. §5, наша цена не завязана на их прайсинг).
- `keragon.com/brand` — официальный SVG-логотип, использован для `icon.svg`.

## 2. Карта возможностей (Шаг 1-2 стандарта)

**КРИТИЧЕСКИЙ ВЫВОД (проверено многократным целевым поиском, включая
попытки найти `api.keragon.com`, Swagger/OpenAPI, "Personal Access
Token"/"API Key" в разделе аккаунта для управления СВОИМИ workflows):
у Keragon НЕТ публичного management REST API**, сравнимого с
Make/n8n/Salesforce/HubSpot (никакого `GET /workflows`, `POST /workflows/{id}/run`,
`GET /executions` и т.п. для стороннего клиента). Это архитектурно тот
же случай, что уже решён для Zapier (см.
`Apps/Zapier Connector/CONNECTOR_DISCOVERY.md`) — узкая, а не CRUD-поверхность.

Реально существующие направленные поверхности:

| Поверхность | Направление | Что реально даёт | Auth |
|---|---|---|---|
| **HTTP Webhook Trigger** (help.keragon.com, Triggers) | Ingress со стороны Keragon (Imperal → Keragon) | Каждый workflow в Keragon можно запустить, отправив HTTP POST на его уникальный webhook URL, сгенерированный самим Keragon при настройке триггера. Это конечный, per-workflow URL — не общий API. | Нет отдельного механизма аутентификации Keragon-стороны сверх самого URL (аналогично Zapier Catch Hook); опционально пользователь настраивает проверку заголовка/подписи на своей стороне workflow, если Keragon это позволяет в самом workflow-условии (уточняется по месту, не гарантированная платформенная фича). |
| **HTTP Client action** (help.keragon.com, Actions) | Egress со стороны Keragon (Keragon → Imperal) | Шаг ВНУТРИ workflow Keragon, который делает произвольный HTTP-запрос (метод/URL/заголовки/тело) к любому внешнему API. Пользователь конфигурирует этот шаг САМ внутри Keragon, указывая наш webhook URL как цель. | Заголовок/секрет добавляется пользователем вручную в конфигурации HTTP Client action на стороне Keragon; со стороны Imperal — обычная секрет-заголовок-проверка на входящем webhook. |
| **`docs.keragon.com` connector CLI/SDK** (`@keragon/connector-sdk`) | Ingress — Imperal становится ОДНИМ ИЗ 300+ built-in коннекторов Keragon | Полноценная интеграция: реальные триггеры/экшены внутри самого Keragon canvas, доступные всем клиентам Keragon. Требует прохождения их ревью ("Claiming your connector"), публикации в их каталоге — отдельный, гораздо больший проект вне контроля Imperal, аналог опции 3 из Zapier-discovery. НЕ строится в этом заходе. |
| **Keragon MCP** (`keragon.com/mcp`) | Both, но это API САМОГО Keragon для AI-агентов | Даёт ChatGPT/Claude/voice-агентам доступ к системам, УЖЕ подключённым внутри Keragon (EHR/CRM и т.д.) — не поверхность для управления самими Keragon-воркфлоу извне, и не то, что коннектор Imperal может использовать как backend. |

**Решение по объёму (аналог Zapier Webhook, но НЕ идентичный код):**
приложение строится как **двусторонний webhook-мост** — то же
архитектурное семейство, что Zapier Webhook, с полным набором функций,
достижимых в этих рамках (Ярус 1+2 ниже), плюс существенный Ярус 3
(наша добавленная ценность), которого у Zapier Webhook нет: healthcare-
специфичные value-add функции (шаблоны событий intake/appointment/
billing, HIPAA-осознанный лог с редактированием PHI-подобных полей,
множественные именованные workflow-мосты вместо одного URL).

### Ярус 1 — Ключевые функции (Key Functions)

1. `set_outgoing_webhook` — сохранить Keragon HTTP Webhook Trigger URL,
   на который будет отправляться событие (запускает конкретный workflow
   Keragon).
2. `send_workflow_event` — отправить произвольный JSON payload на
   сохранённый Keragon workflow URL (эквивалент "run this Keragon
   workflow now").
3. `get_outgoing_webhook_status` — прочитать, настроен ли исходящий мост.
4. `get_inbound_webhook_config` — прочитать наш собственный входящий URL
   + статус общего секрета (для вставки в HTTP Client action Keragon).
5. `regenerate_inbound_secret` — сгенерировать новый секрет (ротация).
6. `list_inbound_events` — прочитать последние события, присланные
   Keragon-воркфлоу через HTTP Client action.

### Ярус 2 — Полное покрытие (Full Coverage)

- `included`: все 6 функций Яруса 1, ПЛЮС расширение до множественных
  именованных мостов (не один webhook URL, а список — Keragon-клиенты
  типично имеют десятки workflow: intake, reminders, billing, no-show,
  referrals — один URL был бы слишком узким по сравнению даже с Zapier
  Webhook, где один Zap = один сценарий, но у Keragon workflow гранулярнее
  и их реально много одновременно активных). → `create_outgoing_bridge`,
  `list_outgoing_bridges`, `update_outgoing_bridge`, `delete_outgoing_bridge`,
  `send_workflow_event` (по имени/id моста).
- `included`: `bulk_send_workflow_events` — отправить одно и то же
  событие (или пакет разных) сразу на несколько мостов за один вызов
  (например: одновременно уведомить workflow "New Patient" и workflow
  "CRM Sync" при создании клиента в другом приложении Imperal).
- `included`: события инбаунда получают `event_kind` (свободный тег,
  который клиент Keragon указывает в теле HTTP Client action — например
  "appointment.booked", "intake.completed") — `list_inbound_events`
  поддерживает фильтр по нему.
- `deferred`: полноценная регистрация Imperal как built-in Keragon
  connector (`docs.keragon.com` CLI-путь) — требует внешнего ревью
  Keragon, отдельный гораздо больший проект, не входит в этот заход;
  триггер для будущего запуска — явное решение Влада пройти этот путь.
- `not applicable`: Keragon MCP — это их API для AI-агентов к ИХ
  подключённым системам, не подходит под модель "коннектор Imperal к
  Keragon".

### Ярус 3 — Функции на нашей стороне (Imperal-side value-add)

1. **Именованные мосты с метаданными** (`create_outgoing_bridge` с
   `name`/`description`) вместо единственного анонимного URL — сервис
   сам по себе не даёт способа помечать/группировать несколько
   webhook-целей, мы вводим это как структуру поверх голого URL.
2. **`bulk_send_workflow_events`** — отправка одного события сразу на
   несколько мостов, которой в самом Keragon (со стороны HTTP Webhook
   Trigger) нет — каждый триггер там принимает только собственный
   единичный POST.
3. **Фильтруемый `event_kind` на входящем логе** — Keragon сам никак не
   классифицирует то, что шлёт через HTTP Client action (это просто
   произвольный HTTP-запрос); мы вводим лёгкую свободную таксономию
   поверх сырых событий для удобной последующей фильтрации в чате/панели.
4. **`audit_bridge_health`** — агрегирующий отчёт: сколько исходящих
   мостов настроено, сколько входящих событий получено за последние N
   дней по каждому `event_kind`, есть ли мосты без единой успешной
   доставки (потенциально сломанный URL на стороне Keragon) — то, чего
   ни один единичный вызов Keragon не даёт, потому что Keragon вообще не
   выставляет наружу свою историю доставок с нашей стороны моста.

## 3. Архитектурное ограничение — обязательно к прочтению перед Фазой 3

Как и Zapier Webhook, это НЕ CRUD-коннектор с листингом/запуском чужих
workflow по id — потому что Keragon не даёт такой API. Название в
Marketplace — **"Keragon"** (без уточнения "Webhook" в display-имени,
т.к. app_id и описание уже проговаривают модель моста явно, аналогично
тому, что n8n/Make называются без суффикса, а Zapier — единственное
исключение, получившее суффикс "Webhook" из-за прямого столкновения с
уже существующим ожиданием "Zapier = полноценный коннектор"). app_id:
`keragon-connector`.

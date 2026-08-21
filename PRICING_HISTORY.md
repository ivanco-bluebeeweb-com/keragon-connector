# Pricing History — Keragon Connector

Обязательный журнал: каждое выставление или изменение цен на функции этого
приложения фиксируется здесь ДО публикации/подачи на ревью — что изменилось,
почему, и на основании чего. Не переписывать прошлые записи — только
дописывать новые сверху.

---

## 2026-08-21 — первичный прайсинг, ДО подачи на ревью

**Контекст:** прайсинг — обязательная часть дефолтного поведения при
разработке ЛЮБОГО приложения, ВСЕГДА выставляется до `submit_for_review`,
в той же сессии, что и `deploy_app` (правило зафиксировано после
инцидента с MuleSoft Connector). Для Keragon Connector применено сразу
после успешного `deploy_app` (19/21 проверок, статус `warning`, не
`rejected` — остаточные warning'и некритичны: длина тестового файла и
литерал "secret" в фикстуре теста), до какой-либо попытки подать на
ревью.

**Метод применения — `developer.update_pricing`** (подтверждённо рабочий
метод, см. канонический `PRICING_POLICY.md` §3 и прецеденты Zapier
Webhook / MuleSoft Connector / Asana Connector / CircleCI Connector).
`save_pricing` НЕ использовался. `pricing_config` передан как настоящий
вложенный JSON-объект (НЕ экранированная строка — ровно та ошибка,
которая ловила Asana Connector 5 раз подряд). `revenue_split_dev=95`
передан ЯВНЫМ отдельным параметром вызова (partner-тир этого
разработчика), не только внутри `pricing_config` — ровно то условие,
нарушение которого дважды ловило MuleSoft/Workato Connector.

**Архитектурный контекст, влияющий на категоризацию:** Keragon Connector
— многомостовой двунаправленный webhook-мост (см. `CONNECTOR_DISCOVERY.md`
и `app.py`), той же архитектурной категории, что Zapier Webhook, но с
множественными именованными мостами вместо одного анонимного URL —
отсюда более широкая линейка функций (12 против 6 у Zapier), но та же
логика ценообразования per-функция.

**Цены — фиксированная платформенная шкала {0, 8, 16, 20, 40, 60}, без
исключений и без x1.8-маркапа (Keragon не Google-backed API):**

| Цена | Функции | Обоснование |
|---|---|---|
| 8 | `list_outgoing_bridges`, `get_outgoing_bridge`, `get_inbound_webhook_config`, `list_inbound_events`, `get_inbound_event` | Простое чтение состояния — тот же уровень, что `get_outgoing_webhook_status`/`get_inbound_webhook_config` у Zapier Webhook |
| 16 | `create_outgoing_bridge`, `update_outgoing_bridge`, `delete_outgoing_bridge`, `send_bridge_event`, `regenerate_inbound_secret` | Стандартное одиночное write-действие/CRUD на один мост — тот же уровень, что `set_outgoing_webhook`/`send_webhook_event`/`regenerate_inbound_secret` у Zapier Webhook |
| 40 | `audit_bridge_health` | Tier-3 value-add агрегированный отчёт по всем мостам сразу (кросс-мостовая диагностика, которой у Keragon нет вообще) — тот же уровень, что `audit_cloudhub_environment` у MuleSoft / `get_low_stock_report` у Shopify |
| 60 | `bulk_send_bridge_event` | Та же операция (`send_bridge_event`), повторённая по нескольким мостам разом — тот же уровень, что любая `bulk_*`-функция на платформе (`bulk_run_scenarios`, `bulk_cancel_pipelines` и т.д.) |

Бесплатных функций в этом приложении нет: в отличие от коннекторов с
OAuth/API-key подключением, у Keragon Connector нет отдельного шага
"подключить аккаунт" — первое действие пользователя уже является
платной write-операцией (`create_outgoing_bridge`) либо бесплатным
чтением (`list_outgoing_bridges` и т.д., оценены в 8, не 0, так как это
не служебное подключение, а обычное чтение прикладных данных).

`pricing_model = "per_action"`, `monthly_price = 0`, `revenue_split_dev = 95`
(partner-тир).

**Источник истины продублирован в `tool-prices.json`** этого приложения
(12/12 функций), по тому же правилу, что и у Zapier Webhook/MuleSoft/
CircleCI Connector.

**Известное ограничение read-back (задача #2113, исполнитель Val, ещё
открыта на момент этой записи):** ни `update_pricing`, ни
`marketplace.get_app_details` не подтверждают программно, что
`tool_prices` реально сохранился — API лишь эхо-отражает отправленный
запрос. Финальное визуальное подтверждение остаётся за человеком:
Developer → My Apps → Keragon → Pricing.

# Keragon Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на функционале `keragon-connector` (bridge к Keragon workflows).

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(account) + `ui.Divider` + navigation `ui.ListItem`(Outgoing Bridges/Inbound Events) + `ui.Button`("App settings") | Без карточек по стандарту. |
| Outgoing Bridges List (center, `center_overlay=True`) | `ui.DataTable`(name, description, created; sortable) + `ui.Button`("Создать bridge") | Табличный обзор именованных мостов к Keragon workflow. |
| Bridge Detail | Back-button + `ui.KeyValue`(trigger URL — маскировано, description) + `ui.Row`(Button "Send Test Event", "Edit", "Delete") | `KeyValue` для метаданных моста, действия по строке в Row. |
| Create/Edit Bridge Form | `ui.Form`(action="create_outgoing_bridge") + `ui.Input`(name) + `ui.Input`(trigger_url, placeholder="https://hooks.keragon.com/...") + `ui.TextArea`(description) | Прямая форма — параметров немного, отдельного мастера не требуется. |
| Send Event Dialog | `ui.Dialog`(title="Отправить событие?", content=`ui.TextArea`(param_name="payload_json", placeholder="JSON payload события..."), confirm_label="Отправить") | Отправка тестового события в реальный Keragon workflow — обязателен `Dialog` с подтверждением содержимого. |
| Inbound Events List | `ui.Select`(event_kind_filter) + `ui.DataTable`(event_kind, received_at, preview; sortable) | Табличный обзор входящих событий от Keragon workflows (POST в наш webhook). |
| Inbound Event Detail | Back-button + `ui.Code`(language="json", full body+headers, readonly) | `Code`(json) для полного просмотра сырого payload события. |
| App Settings | `ui.Accordion`([Inbound Webhook URL + Regenerate Secret]) | Централизованные настройки по стандарту — здесь нет "Connections" в привычном смысле, только webhook config. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__keragon_sidebar` рендерит account + разделы,
   `auto_action` открывает Outgoing Bridges List.
2. "Создать bridge" → Create Bridge Form → `ui.Call("create_outgoing_bridge")` →
   `refresh_panels` на список.
3. Клик на bridge → Bridge Detail → "Send Test Event" → `ui.Dialog` с JSON payload
   → `ui.Call("send_bridge_event")`.
4. Inbound Events List — read-only лог того, что Keragon уже прислал нам; клик на
   событие → Inbound Event Detail с полным JSON.
5. App Settings — только через кнопку в сайдбаре; содержит Regenerate Secret
   (destructive-lite: старый секрет сразу перестаёт работать) — оформляется как
   отдельная кнопка с `ui.Dialog` подтверждением внутри Accordion секции.

## 3. Экраны/карточки (артефакты для реализации)

- `panels.py`: `__panel__keragon_sidebar` (left).
- `panels_bridges.py`: `__panel__bridge_list` (center, `center_overlay=True`),
  `__panel__bridge_detail` (center, параметризован `bridge_id`),
  `__panel__bridge_form` (center overlay, создание/редактирование).
- `panels_inbound.py`: `__panel__inbound_events_list` (center),
  `__panel__inbound_event_detail` (center, параметризован `event_id`, Code json).
- `panels_settings.py`: `__panel__app_settings` (center overlay, Accordion,
  webhook URL + regenerate secret).

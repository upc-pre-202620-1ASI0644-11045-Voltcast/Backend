# Integración de OneDrive

Un supervisor conecta **una cuenta de OneDrive de la empresa** (cuenta personal de Microsoft, dedicada). El backend la usa para traer los Excel de voltajes. La app nunca ve el código de autorización ni los tokens: solo llama a estos endpoints y abre la pantalla de Microsoft en el navegador externo.

Base: `/api/v1/integrations/onedrive`. Autenticación `Authorization: Bearer <jwt>`, salvo en el callback. Los errores tienen el formato de siempre: `{"detail": "texto"}`.

## Endpoints

| Endpoint | Acceso | Éxito | Errores |
|---|---|---|---|
| `GET /connect` | Solo supervisor (`ADMIN`) | `200 {"authorizationUrl": "https://login.microsoftonline.com/..."}` | `401`, `403 Supervisor role required`, `503 OneDrive integration is not configured` |
| `GET /callback?code&state` | Público (lo llama Microsoft) | `200` página "Listo, vuelve a VoltCast" | `400` página genérica "No se pudo completar la conexión..." (sin detalle) |
| `GET /status` | Cualquier usuario activo | `200` (abajo) | `401` |
| `DELETE /` | Solo supervisor | `204` sin cuerpo (idempotente) | `401`, `403` |

`POST /sync` no existe: la sincronización corre sola cada día (ver más abajo).

### `GET /status`

```json
{ "connected": true, "account": "empresa@outlook.com", "lastSyncAt": "2026-11-11T08:00:12Z", "error": null, "connectedAt": "2026-11-01T09:00:00Z" }
```

- Sin conexión: `connected: false` y el resto `null`.
- `error`: `null`, `"invalid_grant"` o `"sync_failed"`.
  - `invalid_grant`: Microsoft ya no acepta la conexión. La app muestra "Reconexión necesaria" y el supervisor pulsa de nuevo "Conectar OneDrive". La sincronización queda detenida hasta entonces.
  - `sync_failed`: la última ejecución falló (red, Microsoft...). Se reintenta sola en la siguiente.
- Con `error != null`, `connected` sigue en `true`: hay una conexión registrada pero rota.
- `lastSyncAt` es la última ejecución que terminó sin error: no cambia si la siguiente falla.

### Flujo

1. El supervisor pulsa "Conectar OneDrive" → la app llama a `GET /connect`.
2. La app abre `authorizationUrl` en el navegador externo; el supervisor inicia sesión y acepta.
3. Microsoft redirige al callback del backend, que valida el `state` (aleatorio, de un solo uso, caduca a los 10 minutos y va ligado al supervisor), guarda el token **cifrado** y muestra la página de "Listo".
4. La app consulta `GET /status`.

Una sola conexión para toda la empresa: volver a conectar la reemplaza, y si dos supervisores conectan a la vez gana la última completada. Retirar a un supervisor del sistema no rompe la conexión; la rompen un cambio de contraseña de la cuenta de OneDrive, MFA, revocar sesiones, desactivarla o ~90 días sin renovar el token. Desconectar borra el token pero conserva los datasets ya traídos.

## Qué se sincroniza

Los Excel (`.xlsx`, `.xlsm`, `.xls`) de la carpeta **`/VoltCast/datasets`** de la cuenta (solo ese nivel, sin subcarpetas). Se dejan ahí a diario o como máximo una vez al mes; pueden traer solo los días nuevos o todo el histórico.

Job `python -m worker onedrive`, una vez al día (**08:00 UTC**, 03:00 en Perú). Cada archivo (por id y versión) se mira una sola vez:

1. Se ignora lo que no sea Excel y lo modificado hace menos de 60 s.
2. Se valida formato, tamaño (100 MB) y fechas (nada posterior a hoy).
3. **Continuidad:** debe añadir días después del último dato (el último dataset `ready` más los archivos ya aceptados) sin dejar más de 12 días sin registros.
   - Sin días nuevos, o ilegible: **rechazado** (no se usa).
   - Con un hueco mayor: **en espera** hasta que lleguen los días intermedios.
   - Si no: **pendiente**.
4. **Puerta de reentrenamiento:** hasta que los pendientes sumen **30 días nuevos** no se crea nada ni se entrena. Con 30 o más se crea **un dataset** con todos ellos que complementa al último dataset `ready` sin pedir confirmación; el ETL lo limpia y, como siempre, entrena con él. La primera vez (sin ningún dataset) basta con los días mínimos que pide el ETL.
5. Si hay un entrenamiento en curso, los archivos siguen pendientes y se intenta al día siguiente.

El motivo de cada archivo queda en la tabla `onedrive_file`. Los datasets resultantes se ven en `GET /api/v1/datasets` como cualquier otro.

Si el token falla con `invalid_grant`, el job marca el error y **no vuelve a intentarlo** hasta que se reconecte.

## Variables de entorno

| Variable | Dónde | Descripción |
|---|---|---|
| `MS_CLIENT_ID` | API y Job | Id de la app registrada en Azure. |
| `MS_CLIENT_SECRET` | API y Job | Client secret. **Caduca como máximo a los 24 meses: anotar la fecha de renovación.** |
| `MS_TENANT_ID` | API y Job | `consumers` (cuenta personal), `common` o el id del tenant (cuenta de trabajo/escuela). |
| `MS_REDIRECT_URI` | API y Job | `https://<backend>/api/v1/integrations/onedrive/callback`. HTTPS, salvo `http://localhost` en desarrollo. |
| `TOKEN_ENCRYPTION_KEY` | API y Job | Clave Fernet: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Si se pierde hay que reconectar. |
| `ONEDRIVE_FOLDER` | Job (opcional) | Carpeta de la cuenta. Por defecto `/VoltCast/datasets`. |

Todo cae en el App Service; el deploy crea el Job `job-voltcast-onedrive` (y lo mantiene al día) cuando `MS_CLIENT_ID` y `TOKEN_ENCRYPTION_KEY` ya están ahí.

## Registro en Azure (lo hace el equipo)

1. Microsoft Entra ID → App registrations → New registration, con cuentas **personales de Microsoft** como tipo admitido.
2. Redirect URI de tipo *Web* con el valor de `MS_REDIRECT_URI`.
3. Certificates & secrets → New client secret.
4. API permissions → Microsoft Graph → delegados: `Files.Read`, `offline_access`, `User.Read`.
5. En la cuenta de OneDrive: crear la carpeta `VoltCast/datasets`.
6. Guardar las credenciales de recuperación de la cuenta: si se pierde el acceso, se pierde la integración.

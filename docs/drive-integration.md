# Integración de Google Drive

Un supervisor conecta **una cuenta de Google Drive de la empresa** (cuenta de Google dedicada). El backend la usa para traer los Excel de voltajes. La app nunca ve el código de autorización ni los tokens: solo llama a estos endpoints y abre la pantalla de Google en el navegador externo.

Base: `/api/v1/integrations/drive`. Autenticación `Authorization: Bearer <jwt>`, salvo en el callback. Los errores tienen el formato de siempre: `{"detail": "texto"}`.

## Endpoints

| Endpoint | Acceso | Éxito | Errores |
|---|---|---|---|
| `GET /connect` | Solo supervisor (`ADMIN`) | `200 {"authorizationUrl": "https://accounts.google.com/o/oauth2/v2/auth?..."}` | `401`, `403 Supervisor role required`, `503 Drive integration is not configured` |
| `GET /callback?code&state` | Público (lo llama Google) | `200` página "Listo, vuelve a VoltCast" | `400` página genérica "No se pudo completar la conexión..." (sin detalle) |
| `GET /status` | Cualquier usuario activo | `200` (abajo) | `401` |
| `DELETE /` | Solo supervisor | `204` sin cuerpo (idempotente) | `401`, `403` |

`POST /sync` no existe: la sincronización corre sola cada día (ver más abajo).

### `GET /status`

```json
{ "connected": true, "account": "empresa@gmail.com", "lastSyncAt": "2026-11-11T08:00:12Z", "error": null, "connectedAt": "2026-11-01T09:00:00Z" }
```

- Sin conexión: `connected: false` y el resto `null`.
- `error`: `null`, `"invalid_grant"` o `"sync_failed"`.
  - `invalid_grant`: Google ya no acepta la conexión. La app muestra "Reconexión necesaria" y el supervisor pulsa de nuevo "Conectar Drive". La sincronización queda detenida hasta entonces.
  - `sync_failed`: la última ejecución falló (red, Google, carpeta mal configurada...). Se reintenta sola en la siguiente.
- Con `error != null`, `connected` sigue en `true`: hay una conexión registrada pero rota.
- `lastSyncAt` es la última ejecución que terminó sin error: no cambia si la siguiente falla.

### Flujo

1. El supervisor pulsa "Conectar Drive" → la app llama a `GET /connect`.
2. La app abre `authorizationUrl` en el navegador externo; el supervisor inicia sesión y acepta. Como la app de Google no está verificada, verá "Google no ha verificado esta app": **Configuración avanzada → Ir a VoltCast (no seguro)**.
3. Google redirige al callback del backend, que valida el `state` (aleatorio, de un solo uso, caduca a los 10 minutos y va ligado al supervisor), guarda el token **cifrado** y muestra la página de "Listo".
4. La app consulta `GET /status`.

Una sola conexión para toda la empresa: volver a conectar la reemplaza, y si dos supervisores conectan a la vez gana la última completada. Retirar a un supervisor del sistema no rompe la conexión; la rompen revocar el acceso de la app en la cuenta de Google, un cambio de contraseña que cierre sesiones, eliminar la cuenta o ~6 meses sin usar el token. Desconectar borra el token del backend pero conserva los datasets ya traídos.

## Qué se sincroniza

Los Excel (`.xlsx`, `.xlsm`, `.xls`) de la carpeta de Drive cuyo id está en `GOOGLE_DRIVE_FOLDER_ID` (solo ese nivel, sin subcarpetas). Se dejan ahí a diario o como máximo una vez al mes; pueden traer solo los días nuevos o todo el histórico. Deben estar subidos **como Excel**: las hojas de cálculo de Google (Sheets) no se leen.

Job `python -m worker drive`, una vez al día (**08:00 UTC**, 03:00 en Perú). Cada archivo (por id y versión) se mira una sola vez:

1. Se ignora lo que no sea Excel y lo modificado hace menos de 60 s.
2. Se valida formato, tamaño (100 MB) y fechas (nada posterior a hoy).
3. **Continuidad:** debe añadir días después del último dato (el último dataset `ready` más los archivos ya aceptados) sin dejar más de 12 días sin registros.
   - Sin días nuevos, o ilegible: **rechazado** (no se usa).
   - Con un hueco mayor: **en espera** hasta que lleguen los días intermedios.
   - Si no: **pendiente**.
4. **Puerta de reentrenamiento:** hasta que los pendientes sumen **30 días nuevos** no se crea nada ni se entrena. Con 30 o más se crea **un dataset** con todos ellos que complementa al último dataset `ready` sin pedir confirmación; el ETL lo limpia y, como siempre, entrena con él. La primera vez (sin ningún dataset) basta con los días mínimos que pide el ETL.
5. Si hay un entrenamiento en curso, los archivos siguen pendientes y se intenta al día siguiente.

El motivo de cada archivo queda en la tabla `drive_file`. Los datasets resultantes se ven en `GET /api/v1/datasets` como cualquier otro.

Si el token falla con `invalid_grant`, el job marca el error y **no vuelve a intentarlo** hasta que se reconecte.

## Variables de entorno

| Variable | Dónde | Descripción |
|---|---|---|
| `GOOGLE_CLIENT_ID` | API y Job | Id del cliente OAuth (tipo Web) de Google Cloud. |
| `GOOGLE_CLIENT_SECRET` | API y Job | Secret del cliente. |
| `GOOGLE_REDIRECT_URI` | API y Job | `https://<backend>/api/v1/integrations/drive/callback`, igual que en el cliente OAuth (sin barra final). HTTPS, salvo `http://localhost` en desarrollo. |
| `GOOGLE_DRIVE_FOLDER_ID` | Job | Id de la carpeta de Drive (lo que va después de `/folders/` en su URL). |
| `TOKEN_ENCRYPTION_KEY` | API y Job | Clave Fernet: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Si se pierde hay que reconectar. |

Todo cae en el App Service; el deploy crea el Job `job-voltcast-drive` (y lo mantiene al día) cuando `GOOGLE_CLIENT_ID` y `TOKEN_ENCRYPTION_KEY` ya están ahí.

## Configuración en Google Cloud (lo hace el equipo)

1. Crear un proyecto y activar **Google Drive API**.
2. Pantalla de consentimiento de OAuth: usuario **Externo**, con nombre, correo de soporte, página principal y política de privacidad (URL públicas), y el dominio de esas páginas en "Dominios autorizados".
3. Acceso a los datos: solo el permiso `.../auth/drive.readonly`.
4. **Publicar la app ("En producción")**. En modo *Testing* el refresh token caduca a los 7 días.
5. Clientes → crear un cliente de tipo **Aplicación web**, con el redirect URI de `GOOGLE_REDIRECT_URI` (y `http://localhost:8000/...` para desarrollo si hace falta).
6. En la cuenta de Drive: crear la carpeta de datasets y copiar su id.
7. Guardar las credenciales de recuperación de la cuenta: si se pierde el acceso, se pierde la integración.

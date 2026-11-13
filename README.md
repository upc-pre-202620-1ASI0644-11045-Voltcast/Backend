# VoltCast — Aplicación móvil con bibliotecas de Machine Learning para pronosticar variaciones de voltaje eléctrico en una industria química peruana

Backend de VoltCast (FastAPI). Equipo: Oscar Gabriel Aranda Vallejos (Scrum Master) · Renzo Cesar Silva Morales (Project Manager).

## Objetivo del sprint 2

Desarrollar los módulos de **Gestión de Usuarios y Accesos** (`iam`) y **Gestión de Celdas y Componentes** (`cell_management`), correspondientes a las HU US009 – US023. Fecha límite: **24/10/2026**.

## Bounded Contexts

| Bounded context             | Módulo                             | Tablas                                                                                                  |
| --------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `iam`                     | Gestión de Usuarios y Accesos      | `role`, `user`, `password_reset`                                                                  |
| `cell_management`         | Gestión de Celdas y Componentes    | `cell`, `component`                                                                                 |
| `dataset_management`      | Ingesta y Preprocesamiento de Datos | `uploaded_dataset`                                                                                    |
| `voltage_forecasting`     | Machine Learning                    | `ml_model`, `training_execution`, `prediction`, `model_evaluation`, `model_evaluation_result` |
| `notification_management` | Alertas y Notificaciones            | `alert_rule`, `notification`, `notification_type`                                                 |

## Product Backlog

### Dataset Management Bounded Context

| ID    | Como                | Quiero                                                                                         | Para                                                                    |
| ----- | ------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| US001 | Ingeniero de Planta | subir archivos Excel con registros de voltaje                                                  | tener un modelo entrenado con los patrones de la empresa                |
| US002 | Ingeniero de Planta | contar con un sistema que identifique el tipo de columnas que tiene un archivo Excel           | determinar rápidamente las columnas con valores de voltaje y corriente eléctrica |
| US003 | Ingeniero de Planta | contar con un sistema que identifique las celdas eléctricas de un archivo Excel                | tener un modelo adaptado a las condiciones actuales de la planta        |
| US004 | Ingeniero de Planta | contar con un sistema que ordene los registros de un archivo Excel                             | evitar valores duplicados y datos no relacionados con el voltaje        |

#### Criterios de aceptación

##### US001 · Subir archivos Excel con registros de voltaje

- **E01: Carga exitosa de un archivo válido**
  - **Dado que** el Ingeniero de Planta está autenticado en el sistema
  - **Y** cuenta con un archivo CSV o Excel con registros de voltaje
  - **Cuando** el ingeniero sube el archivo al sistema
  - **Entonces** el sistema muestra la confirmación del registro exitoso.
- **E02: Archivo con formato inválido**
  - **Dado que** el Ingeniero de Planta está autenticado en el sistema
  - **Y** el archivo seleccionado tiene una extensión no soportada
  - **Cuando** el ingeniero intenta subir el archivo
  - **Entonces** el sistema rechaza la carga
  - **Y** muestra un mensaje de error especificando la causa del rechazo.

##### US002 · Identificar el tipo de columnas de un archivo Excel

- **E01: Identificación correcta de columnas**
  - **Dado que** el Ingeniero de Planta carga un archivo Excel en el sistema
  - **Y** el archivo cuenta con encabezados reconocibles de voltaje, corriente y factor de potencia
  - **Cuando** el sistema procesa el archivo
  - **Entonces** el sistema identifica y clasifica correctamente cada columna según su tipo.
- **E02: Columnas no identificables**
  - **Dado que** el Ingeniero de Planta carga un archivo Excel en el sistema
  - **Y** el archivo no cuenta con encabezados reconocibles
  - **Cuando** el sistema intenta identificar el tipo de columnas
  - **Entonces** el sistema muestra un mensaje indicando que no pudo identificar columnas
  - **Y** solicita al usuario verificar la estructura del archivo.

##### US003 · Identificar las celdas eléctricas de un archivo Excel

- **E01: Identificación exitosa de celdas eléctricas**
  - **Dado que** el Ingeniero de Planta carga un archivo Excel con registros de celdas eléctricas
  - **Cuando** el sistema procesa el archivo
  - **Entonces** el sistema identifica correctamente cada celda eléctrica registrada, indicando el número de celdas eléctricas.
- **E02: Archivo sin celdas reconocibles**
  - **Dado que** el Ingeniero de Planta ha cargado un archivo Excel que no contiene registros identificables como celdas eléctricas
  - **Cuando** el sistema intenta identificar las celdas
  - **Entonces** el sistema muestra un mensaje indicando que no se encontraron celdas eléctricas.

##### US004 · Ordenar los registros de un archivo Excel

- **E01: Ordenamiento y limpieza exitosa**
  - **Dado que** el Ingeniero de Planta carga un archivo Excel
  - **Y** el sistema identifica correctamente las columnas y celdas eléctricas
  - **Cuando** el sistema procesa los registros del archivo
  - **Entonces** el sistema ordena los registros y elimina los datos duplicados o no relacionados con el voltaje.
- **E02: Detección de registros duplicados**
  - **Dado que** el archivo contiene registros duplicados
  - **Cuando** el sistema realiza el proceso de limpieza
  - **Entonces** el sistema conserva únicamente un registro por cada valor duplicado
  - **Y** descarta los datos no relacionados con el voltaje.

### Cell Management Bounded Context

| ID    | Como                | Quiero                                                                             | Para                                                                      |
| ----- | ------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| US009 | Ingeniero de Planta | registrar las celdas eléctricas de la empresa                                     | tener un registro sólido en el sistema                                   |
| US010 | Ingeniero de Planta | editar los datos de una celda eléctrica                                           | mantener la información de las celdas eléctricas actualizada            |
| US011 | Ingeniero de Planta | deshabilitar una celda eléctrica que esté fuera de uso, conservando su historial | mantener en el sistema solamente las celdas con las que cuenta la empresa |
| US012 | Ingeniero de Planta | registrar y asignar los cátodos y ánodos de cada celda                           | mantener un inventario actualizado de los componentes instalados          |
| US013 | Ingeniero de Planta | deshabilitar un cátodo o ánodo que esté fuera de uso, conservando su historial  | tener un registro permanente y trazable de estos componentes              |
| US014 | Ingeniero de Planta | intercambiar los cátodos y ánodos asignados entre celdas                         | regular la carga de voltaje                                               |
| US015 | Ingeniero de Planta | editar los datos de un cátodo o ánodo                                            | mantener su información actualizada a lo largo del tiempo                |
| US016 | Ingeniero de Planta | generar un código de barras por celda                                             | identificar cada celda de forma única                                    |
| US017 | Ingeniero de Planta | descargar el código de barras de una celda                                        | imprimirlo y usarlo para identificar la celda en planta                   |

### IAM Bounded Context

| ID    | Como                        | Quiero                                                                                         | Para                                                                                           |
| ----- | --------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| US018 | Supervisor                  | visualizar las solicitudes de registro pendientes desde un panel                               | revisarlas de manera rápida                                                                   |
| US019 | Supervisor                  | aprobar o rechazar las solicitudes de registro pendientes                                      | controlar qué personal obtiene acceso al sistema                                              |
| US020 | Supervisor                  | editar o deshabilitar cuentas de ingenieros integradas al sistema                              | asegurar que solo el personal operativo autorizado mantenga acceso al sistema                  |
| US021 | Supervisor e Ing. de Planta | acceder al sistema con credenciales seguras (login)                                            | proteger la privacidad de los datos energéticos de la empresa                                 |
| US022 | Supervisor e Ing. de Planta | recuperar mi contraseña mediante un código de verificación enviado a mi correo electrónico | recuperar el acceso a mi cuenta de forma segura en caso de olvido                              |
| US023 | Ingeniero de Planta         | completar un formulario de registro (sign up) que genere una solicitud de creación de cuenta  | poder solicitar el acceso al sistema bajo el permiso de un supervisor con credenciales propias |

### Voltage Forecasting Bounded Context

| ID    | Como       | Quiero                                                        | Para                                         |
| ----- | ---------- | ------------------------------------------------------------- | -------------------------------------------- |
| US005 | Ingeniero de Planta | contar con un modelo predictivo entrenado | generar proyecciones de voltaje |
| US006 | Ingeniero de Planta | poder evaluar la precisión del modelo | conocer la efectividad del sistema |
| US007 | Ingeniero de Planta | visualizar pronósticos de voltaje generados | identificar celdas que superen el voltaje permitido |
| US008 | Ingeniero de Planta | filtrar pronósticos de voltajes por fecha | visualizar pronósticos de una fecha específica |
| US031 | Supervisor | que el sistema detecte automáticamente registros nuevos de voltaje en la nube | que se mantenga con datos actualizados |

#### Criterios de aceptación

##### US005 · Contar con un modelo predictivo entrenado

- **E01: Generación exitosa de proyecciones**
  - **Dado que** el modelo predictivo se encuentra disponible y entrenado con los patrones de la empresa
  - **Cuando** el Ingeniero de Planta solicita generar una proyección de voltaje
  - **Entonces** el sistema genera y muestra las proyecciones de voltaje correspondientes.
- **E02: Modelo en proceso de reentrenamiento**
  - **Dado que** el modelo predictivo está en proceso de reentrenamiento
  - **Cuando** el Ingeniero de Planta intenta generar una proyección
  - **Entonces** el sistema muestra un mensaje indicando que se usará la última versión disponible del modelo y que una nueva versión saldrá próximamente.

##### US006 · Evaluar la precisión del modelo

- **E01: Cálculo exitoso de la precisión del modelo**
  - **Dado que** el modelo predictivo cuenta con proyecciones generadas y datos reales de comparación
  - **Cuando** el Ingeniero de Planta solicita evaluar la precisión del modelo
  - **Entonces** el sistema calcula y muestra las métricas de precisión del modelo.
- **E02: Modelo en proceso de reentrenamiento**
  - **Dado que** el modelo predictivo está en proceso de reentrenamiento
  - **Cuando** el Ingeniero de Planta solicita evaluar la precisión del modelo
  - **Entonces** el sistema muestra un mensaje indicando que se usará la última versión disponible del modelo y que una nueva versión saldrá próximamente.

##### US007 · Visualizar pronósticos de voltaje generados

- **E01: Visualización de pronósticos generados**
  - **Dado que** el sistema cuenta con pronósticos de voltaje generados
  - **Cuando** el Ingeniero de Planta accede a la sección de pronósticos
  - **Entonces** el sistema muestra los pronósticos de voltaje de todas las celdas.
- **E02: Identificación de celdas que superan el voltaje permitido**
  - **Dado que** existen pronósticos que superan el umbral de voltaje permitido
  - **Cuando** el Ingeniero de Planta visualiza los pronósticos
  - **Entonces** el sistema resalta visualmente las celdas cuyo pronóstico excede el voltaje permitido.
- **E03: Visualización exitosa de pronósticos sin conexión a internet**
  - **Dado que** el sistema cuenta con pronósticos previamente consultados
  - **Cuando** el Ingeniero de Planta accede a la sección de pronósticos sin conexión a Internet
  - **Entonces** el sistema muestra pronósticos previamente consultados.
- **E04: Visualización fallida de pronósticos sin conexión a internet**
  - **Dado que** el Ingeniero de Planta no cuenta con pronósticos previamente consultados
  - **Cuando** el Ingeniero de Planta accede a la sección de pronósticos sin conexión a Internet
  - **Entonces** el sistema informa que no existen pronósticos disponibles para su consulta sin conexión.

##### US008 · Filtrar pronósticos de voltajes por fecha

- **E01: Filtrado por fecha exitoso**
  - **Dado que** el sistema cuenta con pronósticos de voltaje generados para distintas fechas
  - **Cuando** el Ingeniero de Planta selecciona una fecha específica
  - **Entonces** el sistema muestra únicamente los pronósticos correspondientes a esa fecha.
- **E02: Filtrado exitoso sin conexión**
  - **Dado que** el sistema cuenta con pronósticos de voltaje previamente sincronizados y almacenados localmente para distintas fechas
  - **Cuando** el Ingeniero de Planta no cuenta con conexión a Internet
  - **Entonces** el sistema muestra únicamente los pronósticos que fueron generados cuando había conexión.
- **E03: Filtrado fallido sin conexión**
  - **Dado que** el sistema no cuenta con pronósticos almacenados localmente para la fecha seleccionada
  - **Cuando** el Ingeniero de Planta no tiene conexión a internet
  - **Entonces** el sistema informa que no existen pronósticos disponibles para su consulta sin conexión.

##### US031 · Detectar automáticamente registros nuevos de voltaje en la nube

- **E01: Conexión exitosa de Google Drive**
  - **Dado que** el Supervisor inicia la conexión con la cuenta de Google Drive de la empresa
  - **Cuando** acepta los permisos en Google y vuelve a VoltCast
  - **Entonces** el sistema muestra la integración como conectada a esa cuenta y sin errores
  - **Y**, si el Supervisor la desconecta, el sistema deja de sincronizar y conserva los datasets ya creados.
- **E02: Detección automática de registros nuevos**
  - **Dado que** Drive está conectado y se suben a la carpeta archivos Excel con voltajes nuevos
  - **Cuando** se ejecuta la sincronización diaria
  - **Entonces** el sistema detecta los archivos sin intervención del Supervisor
  - **Y**, al acumular más de 30 días nuevos, crea un dataset que complementa al último y lo deja listo
  - **Y** el sistema inicia un entrenamiento de forma automática.
- **E03: Acceso no permitido a la conexión**
  - **Dado que** un usuario sin rol de Supervisor intenta conectar Drive
  - **Cuando** solicita la conexión
  - **Entonces** el sistema rechaza la solicitud por falta de permisos
  - **Y** el usuario puede consultar el estado de la integración
  - **Y**, si el enlace de autorización se reutiliza, el sistema muestra un error genérico y no conecta nada.
- **E04: Archivos no procesables**
  - **Dado que** Drive está conectado y la carpeta contiene archivos con problemas
  - **Cuando** se ejecuta la sincronización diaria
  - **Entonces** el sistema rechaza el archivo que no aporta días nuevos, indicando el motivo
  - **Y** retiene el archivo con un hueco de más de 12 días hasta que lleguen los días intermedios
  - **Y** ignora, sin error, las hojas de Google y los archivos que no son Excel.
- **E05: Sincronización diferida**
  - **Dado que** un archivo se modificó hace menos de 60 segundos, o hay un entrenamiento en curso
  - **Cuando** se ejecuta la sincronización diaria
  - **Entonces** el sistema espera a la siguiente ejecución sin fallar ni perder archivos.
- **E06: Fallo de acceso a Google**
  - **Dado que** se revocó el acceso de VoltCast o la carpeta configurada no es válida
  - **Cuando** se ejecuta la sincronización diaria
  - **Entonces** el sistema registra el error en el estado de la integración, sin reintentar ni borrar datos
  - **Y**, al corregir la causa, el error se limpia
  - **Y** ningún registro ni respuesta expone tokens, secretos ni el código de autorización.

### Notification Management Bounded Context

| ID    | Como                                | Quiero                                                                                                          | Para                                                                        |
| ----- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| US024 | Supervisor e Ingeniero de Planta    | recibir una notificación por correo cuando mi contraseña haya sido cambiada                                     | detectar de inmediato un posible acceso no autorizado a mi cuenta          |
| US025 | Supervisor                          | recibir una notificación cuando un visitante solicite acceso al sistema                                         | enterarme rápidamente de nuevas peticiones de acceso                        |
| US026 | Ingeniero de Planta                 | recibir notificaciones cuando algún pronóstico supere el umbral de voltaje permitido en cada celda para una fecha determinada | anotar las celdas que podrían experimentar excesos de voltaje para una fecha determinada |
| US027 | Supervisor                          | configurar el umbral máximo de voltaje                                                                          | ajustar las notificaciones de alerta según las condiciones específicas de la industria |
| US028 | Ingeniero de Planta                 | recibir notificaciones cuando esté cercana la fecha en la que se pronosticó un valor excesivo de voltaje        | recordar las celdas que deben ser revisadas                                 |
| US029 | Ingeniero de Planta                 | recibir una notificación cuando mi cuenta haya sido aceptada en el sistema                                      | saber si ya puedo utilizar el sistema                                       |
| US030 | Ingeniero de Planta                 | recibir una notificación cuando mi cuenta haya sido rechazada en el sistema                                     | saber si tengo permiso de utilizar el sistema                               |

#### Criterios de aceptación

##### US024 · Recibir una notificación por correo cuando mi contraseña haya sido cambiada

- **E01: Notificación exitosa de cambio de contraseña**
  - **Dado que** el usuario decide cambiar su contraseña
  - **Cuando** ingresa una nueva contraseña válida
  - **Entonces** el sistema envía un correo electrónico notificando el cambio al titular de la cuenta.
- **E02: Notificación no enviada**
  - **Dado que** el usuario decide cambiar su contraseña
  - **Cuando** no ingresa una nueva contraseña válida
  - **Entonces** el sistema no envía un correo electrónico notificando el cambio.

##### US025 · Recibir una notificación cuando un visitante solicite acceso al sistema

- **E01: Notificación exitosa de nueva petición de acceso**
  - **Dado que** un visitante envía una solicitud de acceso al sistema
  - **Cuando** este ingresa datos válidos
  - **Entonces** el sistema notifica al Supervisor sobre la nueva petición.
- **E02: Notificación no enviada**
  - **Dado que** un visitante envía una solicitud de acceso al sistema
  - **Cuando** este no rellena correctamente todos los campos pedidos en el registro de su cuenta
  - **Entonces** el sistema no notifica al Supervisor sobre la nueva petición.

##### US026 · Recibir notificaciones cuando algún pronóstico supere el umbral de voltaje permitido

- **E01: Notificación exitosa de exceso de voltaje**
  - **Dado que** el Ingeniero de Planta desea realizar pronósticos de voltaje
  - **Cuando** el sistema obtiene pronósticos donde se excede el umbral máximo permitido para una celda y fecha determinada
  - **Entonces** el sistema notifica el incremento de voltaje al Ingeniero de Planta indicando la celda y fecha determinada.
- **E02: Pronóstico dentro del rango permitido**
  - **Dado que** el Ingeniero de Planta desea realizar pronósticos de voltaje
  - **Cuando** el sistema no obtiene pronósticos donde se excede el umbral máximo permitido para una celda y fecha determinada
  - **Entonces** el sistema no genera ninguna notificación sobre voltaje sobrecargado.

##### US027 · Configurar el umbral máximo de voltaje

- **E01: Configuración exitosa del umbral máximo**
  - **Dado que** el Supervisor ingresa un nuevo valor de umbral máximo de voltaje
  - **Cuando** confirma los cambios
  - **Entonces** el sistema actualiza el umbral.
- **E02: Configuración con valor inválido**
  - **Dado que** el Supervisor ingresa un valor de umbral no numérico o fuera de rango permitido
  - **Cuando** intenta guardar la configuración
  - **Entonces** el sistema rechaza el cambio
  - **Y** muestra un mensaje indicando el error.

##### US028 · Recibir notificaciones cuando esté cercana la fecha de un voltaje excesivo pronosticado

- **E01: Notificación exitosa de proximidad de fecha**
  - **Dado que** el Ingeniero de Planta desea recibir una notificación sobre un voltaje excesivo pronosticado para una fecha próxima
  - **Cuando** el sistema detecta que el tiempo para llegar a la fecha pronosticada es en un día o menos
  - **Entonces** el sistema notifica al Ingeniero de Planta recordándole revisar la celda correspondiente.
- **E02: Notificación no enviada**
  - **Dado que** el Ingeniero de Planta desea recibir una notificación sobre un voltaje excesivo pronosticado para una fecha próxima
  - **Cuando** el sistema detecta que el tiempo para llegar a la fecha pronosticada no es en un día o menos
  - **Entonces** el sistema no notifica al Ingeniero de Planta recordándole revisar la celda correspondiente todavía.

##### US029 · Recibir una notificación cuando mi cuenta haya sido aceptada en el sistema

- **E01: Notificación exitosa de aceptación de cuenta**
  - **Dado que** el Supervisor aprueba la petición de acceso al sistema de un Ingeniero de Planta
  - **Cuando** el sistema registra la aprobación
  - **Entonces** el sistema notifica al ingeniero que su cuenta ha sido aceptada.
- **E02: Notificación inmediata fallida**
  - **Dado que** el Supervisor aprueba la petición de acceso al sistema de un Ingeniero de Planta
  - **Cuando** el Supervisor no cuenta con conexión a Internet para enviar la notificación
  - **Y** el sistema registra la aprobación de manera local
  - **Entonces** el sistema registra la notificación como pendiente de envío para ser enviada cuando se restablezca la conexión.

##### US030 · Recibir una notificación cuando mi cuenta haya sido rechazada en el sistema

- **E01: Notificación exitosa de rechazo de cuenta**
  - **Dado que** el Supervisor rechaza la petición de acceso de un Ingeniero de Planta
  - **Cuando** el sistema registra el rechazo
  - **Entonces** el sistema notifica al ingeniero que su cuenta ha sido rechazada.
- **E02: Notificación inmediata fallida**
  - **Dado que** el Supervisor rechaza la petición de acceso de un Ingeniero de Planta
  - **Cuando** el Supervisor no cuenta con conexión a Internet para enviar la notificación
  - **Y** el sistema registra el rechazo de manera local
  - **Entonces** el sistema registra la notificación como pendiente de envío para ser enviada cuando se restablezca la conexión.

## Backend Stack

- Python 3.13
- FastAPI
- MySQL 8.0 (Azure Database for MySQL)
- Azure Cache for Redis (sesiones y tokens JWT)
- Autenticación: JWT + bcrypt
- SMTP (código de recuperación de contraseña)

## Roles

1) Supervisor: ADMIN
2) Ingeniero de Planta: USER

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

# Aplicación móvil con bibliotecas de Machine Learning para pronosticar variaciones de voltaje eléctrico en una industria química peruana

## Product Backlog

### IAM Bounded Context

| ID    | Como                | Quiero                                                                                                     | Para                                                                                           |
|-------|---------------------|------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| US019 | Supervisor          | visualizar las solicitudes de registro pendientes desde un panel                                           | revisarlas de manera rápida                                                                    |
| US020 | Supervisor          | aprobar o rechazar las solicitudes de registro pendientes                                                  | controlar qué personal obtiene acceso al sistema                                               |
| US021 | Supervisor          | editar o deshabilitar cuentas de ingenieros integradas al sistema                                          | asegurar que solo el personal operativo autorizado mantenga acceso al sistema                  |
| US022 | Supervisor          | crear mi cuenta directamente desde el backend                                                              | evitar la creación descontrolada de perfiles de administrador                                  |
| US023 | Ingeniero de Planta | recuperar mi contraseña mediante un código de verificación enviado a mi correo electrónico                 | recuperar el acceso a mi cuenta de forma segura en caso de olvido                              |
| US024 | Ingeniero de Planta | completar un formulario de registro (sign up) que genere una solicitud de creación de cuenta               | poder solicitar el acceso al sistema bajo el permiso de un supervisor con credenciales propias |
| US025 | Ingeniero de Planta | recibir una notificación por correo electrónico cuando mi contraseña haya sido cambiada                    | detectar de inmediato un posible acceso no autorizado a mi cuenta                              |
| US026 | Ingeniero de Planta | iniciar sesión en la app mediante credenciales otorgadas                                                   | proteger la privacidad de los datos energéticos de la empresa                                  |
| US027 | Supervisor          | recibir una notificación por correo electrónico cuando se genera una nueva solicitud de creación de cuenta | enterarme de nuevas solicitudes de acceso                                                      |

### Backend Stack

- Python 3.13
- FastAPI
- MySQL 8.0
- Docker

### Roles

1) Supervisor: ADMIN
2) Ingeniero de Planta: USER
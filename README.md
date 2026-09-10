# Aplicación móvil con bibliotecas de Machine Learning para pronosticar variaciones de voltaje eléctrico en una industria química peruana

## Product Backlog

### Cell Management Bounded Context

| ID    | Como                | Quiero                                                                           | Para                                                                      |
|-------|---------------------|----------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| US012 | Ingeniero de Planta | registrar las celdas electricas de la empresa                                    | tener un registro sólido en el sistema                                    |
| US013 | Ingeniero de Planta | editar los datos de una celda eléctrica                                          | mantener la información de las celdas eléctricas actualizada              |
| US014 | Ingeniero de Planta | deshabilitar una celda eléctrica que esté fuera de uso, conservando su historial | mantener en el sistema solamente las celdas con las que cuenta la empresa |
| US015 | Ingeniero de Planta | registrar y asignar los cátodos y ánodos de cada celda                           | mantener un inventario actualizado de los componentes instalados          |
| US016 | Ingeniero de Planta | deshabilitar un cátodo o ánodo que esté fuera de uso, conservando su historial   | tener un registro permanente y trazable de estos componentes              |
| US017 | Ingeniero de Planta | intercambiar los cátodos y ánodos asignados en cada celda                        | regular la carga de voltaje                                               |
| US018 | Ingeniero de Planta | editar los datos de un cátodo o ánodo                                            | mantener su información actualizada a lo largo del tiempo                 |


### IAM Bounded Context

| ID    | Como                | Quiero                                                                                                     | Para                                                                                           |
|-------|---------------------|------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| US021 | Supervisor          | visualizar las solicitudes de registro pendientes desde un panel                                           | revisarlas de manera rápida                                                                    |
| US022 | Supervisor          | aprobar o rechazar las solicitudes de registro pendientes                                                  | controlar qué personal obtiene acceso al sistema                                               |
| US023 | Supervisor          | editar o deshabilitar cuentas de ingenieros integradas al sistema                                          | asegurar que solo el personal operativo autorizado mantenga acceso al sistema                  |
| US024 | Supervisor          | crear mi cuenta directamente desde el backend                                                              | evitar la creación descontrolada de perfiles de administrador                                  |
| US025 | Ingeniero de Planta | recuperar mi contraseña mediante un código de verificación enviado a mi correo electrónico                 | recuperar el acceso a mi cuenta de forma segura en caso de olvido                              |
| US026 | Ingeniero de Planta | completar un formulario de registro (sign up) que genere una solicitud de creación de cuenta               | poder solicitar el acceso al sistema bajo el permiso de un supervisor con credenciales propias |
| US027 | Ingeniero de Planta | recibir una notificación por correo electrónico cuando mi contraseña haya sido cambiada                    | detectar de inmediato un posible acceso no autorizado a mi cuenta                              |
| US028 | Ingeniero de Planta | iniciar sesión en la app mediante credenciales otorgadas                                                   | proteger la privacidad de los datos energéticos de la empresa                                  |
| US029 | Supervisor          | recibir una notificación por correo electrónico cuando se genera una nueva solicitud de creación de cuenta | enterarme de nuevas solicitudes de acceso                                                      |

### Backend Stack

- Python 3.13
- FastAPI
- MySQL 8.0
- Docker

### Roles

1) Supervisor: ADMIN
2) Ingeniero de Planta: USER
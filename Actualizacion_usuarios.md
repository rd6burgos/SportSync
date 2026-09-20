## Actualizaciones del proyecto

- [Configuración de usuarios y actualización de la base de datos](ACTUALIZACION_USUARIOS.md)

Actualización: registro, inicio de sesión y base de datos

SportSync ya permite crear una cuenta con nombre, correo y contraseña, iniciar sesión con el correo y cerrar sesión. Las cuentas se guardan en la base de datos local y las contraseñas se almacenan mediante un hash.

Se incorporó la aplicación usuarios y un modelo personalizado llamado Usuario. Los roles de Participante, Organizador y Administrador todavía están pendientes de implementación.

Pasos para actualizar el proyecto

Cuando los cambios estén integrados en main:

Detengan el servidor de Django con Ctrl + C.
Guarden sus cambios pendientes antes de cambiar de rama.
En GitKraken, seleccionen main y hagan Pull.
Abran Anaconda Prompt, activen su entorno y entren a la carpeta que contiene manage.py.
Si ya tenían una base de datos anterior a este cambio

Este cambio sustituye el modelo de usuario original de Django. Si su base anterior solo contiene datos de prueba que no necesitan trasladar, consérvenla como respaldo ejecutando:

ren db.sqlite3 db_antes_usuarios.sqlite3

Ejecuten este paso una sola vez, antes de crear la base con el nuevo modelo. Si ya existe un respaldo con ese nombre, utilicen otro nombre y añádanlo a .gitignore.

Si tienen datos que necesitan conservar en la nueva base, avisen antes de continuar para planificar su traslado.

Crear o actualizar las tablas

Si están clonando el proyecto por primera vez, no necesitan renombrar ninguna base. Ejecuten directamente:

python manage.py migrate

Quienes hayan respaldado la base anterior también deben ejecutar ese comando. Django creará una nueva db.sqlite3 con las tablas correspondientes.

Después comprueben la configuración e inicien el servidor:

python manage.py check
python manage.py runserver

Las migraciones ya están incluidas en el repositorio: no necesitan ejecutar makemigrations para recibir estos cambios.

Pruebas disponibles
Registro: http://127.0.0.1:8000/usuarios/registro/
Inicio de sesión: http://127.0.0.1:8000/usuarios/login/

Cada integrante debe crear su propia cuenta de prueba. Registrarse crea una cuenta normal, sin permisos de administrador ni de organizador.

Qué compartimos por GitHub

Compartimos el código y los archivos de migración, que describen cómo crear las tablas. Cada integrante tiene su propia base de datos local: las cuentas y los datos no se sincronizan mediante Push o Pull.

No deben subir estos archivos:

db.sqlite3
db_antes_usuarios.sqlite3
config/configuracion_local.py

Cada integrante debe conservar su configuración local y su propia SECRET_KEY, siguiendo las instrucciones de instalación del README.
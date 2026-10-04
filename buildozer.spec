[app]

# ---- Datos básicos de la app ----
title = Presupuesto
package.name = presupuesto
package.domain = org.carlos

# Dónde está el código. "." = la raíz del repositorio (donde está este
# mismo archivo buildozer.spec).
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

# Librerías que necesita el proyecto. Revisé presupuesto.py: solo usa la
# librería estándar de Python (json, math, os) y Kivy "a secas", nada de
# kivymd ni otros paquetes, así que con esto alcanza y la compilación es
# más rápida.
requirements = python3,kivy

# La app está pensada para usarse en vertical.
orientation = portrait
fullscreen = 0

# La app guarda su archivo de datos en la carpeta privada que Android le
# da a cada app, así que no necesita pedir permisos de almacenamiento.
android.permissions =

# El SDK de Android pide "aceptar" la licencia de cada paquete antes de
# instalarlo (como tocar "Acepto" en un instalador). Como en GitHub
# Actions no hay nadie ahí para tocar ese botón, sin esta línea la
# compilación se corta con "licenses... were not accepted". Esta línea
# le dice a Buildozer que las acepte él solo, automáticamente.
android.accept_sdk_license = True

# No fijo android.api/minapi/ndk a propósito: así Buildozer siempre usa
# los valores que trae por defecto en la versión que se instale en el
# momento de compilar (se van actualizando solos con el tiempo). Si algún
# día querés fijarlos vos mismo, descomentá y ajustá estas líneas:
# android.api = 34
# android.minapi = 21

# Tu celular (y casi cualquier Android de los últimos años) es de 64
# bits, así que compilamos solo para esa arquitectura: la compilación es
# bastante más rápida. Si alguna vez necesitás instalarlo en un celular
# viejo de 32 bits, agregá ", armeabi-v7a" a la lista de abajo.
android.archs = arm64-v8a

android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1

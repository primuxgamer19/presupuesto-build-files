# Compilar Presupuesto a APK

Como no tenés una PC con Linux a mano, la forma más realista para vos es
dejar que **GitHub Actions** compile el APK en la nube, gratis, y
después descargarlo desde el navegador del celular. Esto SÍ se puede
hacer todo desde el celular.

## 1. Armar el repositorio en GitHub

Necesitás un repositorio con esta estructura exacta:

```
tu-repositorio/
├── main.py
├── presupuesto.py
├── buildozer.spec
└── .github/
    └── workflows/
        └── build.yml
```

- `main.py`, `buildozer.spec` y `.github/workflows/build.yml` son los
  que te acabo de armar: subilos tal cual, sin editarlos.
- `presupuesto.py` es tu archivo de siempre, el mismo que usás en
  Pydroid 3. Cada vez que lo mejores, subí la versión nueva al
  repositorio.

Se puede crear todo esto desde la app de GitHub o desde
github.com en el navegador del celular: creás el repositorio, y subís
cada archivo con "Add file → Upload files" respetando esas carpetas
(al subir `build.yml` escribí la ruta completa `.github/workflows/`
cuando te lo pida, o arrastralo dentro de esa carpeta si la app te deja
crearla).

## 2. Que compile

En cuanto subas los 4 archivos, GitHub Actions arranca solo. Si querés
lanzarlo de nuevo sin cambiar nada (por ejemplo, para reintentar), entrá
a la pestaña **Actions** de tu repositorio y tocá **Run workflow**.

La primera compilación tarda bastante (15-25 minutos, porque tiene que
descargar todo el Android SDK/NDK desde cero). Las siguientes son más
rápidas.

## 3. Descargar el APK

Cuando el workflow termine con un ✓ verde, entrá a esa ejecución (click
en el nombre) y bajá hasta **Artifacts**: ahí vas a encontrar
`presupuesto-apk` para descargar.

## 4. Instalarlo en tu celular

Al ser un APK fuera de Play Store, Android te va a pedir permiso la
primera vez ("instalar apps desconocidas") para la app con la que lo
abriste (Chrome, Archivos, etc.). Se lo das, instalás, y listo.

## Si algo falla

Entrá a la ejecución fallida (❌) en la pestaña Actions y abrí el paso
"Compilar con Buildozer": ahí vas a ver el error exacto. Si no entendés
el mensaje, pegámelo y lo revisamos.

## Compilar en tu propia PC (para más adelante)

El día que tengas una PC con Linux (o WSL en Windows) funcionando, no
hace falta instalar nada manualmente: Buildozer tiene una imagen de
Docker oficial. Desde la carpeta del proyecto:

```bash
docker run --interactive --tty --rm \
    --volume "$HOME/.buildozer":/home/user/.buildozer \
    --volume "$PWD":/home/user/hostcwd \
    kivy/buildozer android debug
```

El APK queda en la carpeta `bin/` del proyecto.

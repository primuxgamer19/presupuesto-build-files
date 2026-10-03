# -*- coding: utf-8 -*-
"""
PRESUPUESTO POR PORCENTAJES  (Kivy, compatible con Pydroid 3)

- Pon tu salario y edítalo cuando quieras.
- Cada categoría tiene un porcentaje del salario.
- Puedes editar el porcentaje, el dinero al mes o el dinero al día en los
  cuadros de texto: los otros dos valores se ajustan solos.
- TAMBIÉN puedes editar tocando directamente el gráfico:
    * Tocas una porción -> se selecciona y aparecen 1 o 2 puntos en sus
      bordes. Arrastras un punto y el tamaño de esa porción cambia en vivo.
    * Hay DOS MODOS para ese arrastre (botón "Modo: ..." debajo del
      gráfico):
        - Adaptativo (por defecto): al mover un punto, la categoría
          vecina que comparte ese borde cede o recibe el espacio.
        - Individual: la categoría vecina NO se mueve. Si encoges,
          se abre un hueco gris justo en ese lugar (no al final).
    * Tocas el área gris (sin asignar, sea al final o un hueco en medio)
      -> aparece un botón "+" que crea una categoría llenando EXACTO
      ese espacio (solo pide el nombre).
- Si un valor no cabe en el porcentaje que queda libre, avisa:
  "No hay suficiente espacio financiero".
- Los datos se guardan en un archivo JSON junto a este script.

Para usarlo en Pydroid 3: instala Kivy desde el menú Pip y ejecuta este archivo.
"""

import json
import math
import os

# ============================================================
#  PARTE 1: LÓGICA DEL PRESUPUESTO (no usa Kivy)
# ============================================================

DIAS_MES = 30          # el gasto diario = gasto mensual / DIAS_MES
TOLERANCIA = 0.005     # margen para errores de redondeo
ARCHIVO = "presupuesto_datos.json"


def a_numero(texto):
    """Convierte '12,5', '$12.50' o '25%' en float. Lanza ValueError si no sirve."""
    t = str(texto).strip()
    t = t.replace("$", "").replace("%", "").replace(" ", "").replace(",", ".")
    if t == "":
        raise ValueError("Escribe un número.")
    try:
        n = float(t)
    except ValueError:
        raise ValueError("'" + str(texto).strip() + "' no es un número válido.")
    if math.isnan(n) or math.isinf(n):
        raise ValueError("Escribe un número válido.")
    return n


def fmt_pct(x):
    """50.0 -> '50', 33.333 -> '33.33'"""
    s = ("%.2f" % x).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def fmt_dinero(x):
    """240.0 -> '240', 8.333 -> '8.33'"""
    if abs(x - round(x)) < TOLERANCIA:
        return str(int(round(x)))
    return "%.2f" % x


def _mas_cercano(angulo, referencia):
    """Los ángulos se repiten cada 360°. Ajusta 'angulo' sumando o
    restando 360 para que quede lo más cerca posible de 'referencia', en
    vez de tomarlo tal cual (0-360). Esto evita que arrastrar un punto
    que cruza la marca de arriba del círculo (0°/360°) haga que el
    ángulo salte de golpe al otro extremo y el porcentaje se vaya a 0."""
    diff = (angulo - referencia + 180.0) % 360.0 - 180.0
    return referencia + diff


class Presupuesto:
    """
    self.categorias es una lista ORDENADA de "segmentos" que se dibujan uno
    tras otro alrededor del círculo. Cada segmento es:
      - una categoría real:  {"nombre": "Comida", "pct": 50.0, "col": 0}
      - un hueco (espacio libre "atrapado" en medio del círculo, creado por
        el modo de arrastre individual): {"nombre": None, "hueco": True,
        "pct": 12.0}
    Además, si la suma de todos los segmentos es menor a 100, queda un
    espacio libre "al final" que NO está en la lista (es implícito).
    "col" es un número fijo asignado a cada categoría cuando se crea, para
    que su color en el gráfico no cambie aunque se creen o quiten huecos
    a su alrededor.
    """

    def __init__(self):
        self.salario = 480.0
        self.categorias = [
            {"nombre": "Comida", "pct": 50.0, "col": 0},
            {"nombre": "Gustos", "pct": 25.0, "col": 1},
            {"nombre": "Fondos", "pct": 25.0, "col": 2},
        ]
        self.siguiente_color = 3

    # ---------- consultas ----------
    def total_pct(self):
        """Suma solo de las categorías reales (los huecos no cuentan como usado)."""
        return sum(c["pct"] for c in self.categorias if not c.get("hueco"))

    def libre_pct(self):
        """Espacio total sin asignar, sumando huecos en medio + el final."""
        libre = 100.0 - self.total_pct()
        return libre if libre > TOLERANCIA else 0.0

    def frontera(self, i):
        """Ángulo acumulado (0-360, convención 'arriba=0, sentido del reloj')
        hasta el borde IZQUIERDO del segmento i (cuenta huecos también,
        porque para la geometría del círculo sí ocupan espacio)."""
        return sum(c["pct"] for c in self.categorias[:i]) * 3.6

    def espacio_final(self):
        """Porcentaje del espacio libre que queda DESPUÉS del último
        segmento (no cuenta los huecos de en medio)."""
        libre = (360.0 - self.frontera(len(self.categorias))) / 3.6
        return libre if libre > TOLERANCIA else 0.0

    def mes(self, pct):
        return self.salario * pct / 100.0

    def dia(self, pct):
        return self.mes(pct) / DIAS_MES

    def maximo_pct(self, i=None):
        """Porcentaje máximo que puede tener la categoría i (i=None: una
        nueva), sumando todo el espacio libre disponible (huecos + final)."""
        otros = sum(c["pct"] for j, c in enumerate(self.categorias)
                    if j != i and not c.get("hueco"))
        return max(0.0, 100.0 - otros)

    def _sin_espacio(self, nombre, maximo):
        msg = "No hay suficiente espacio financiero.\n\n"
        msg += "Para '" + nombre + "' solo puedes destinar como máximo "
        msg += fmt_pct(maximo) + "%"
        if self.salario > 0:
            msg += (" ($" + fmt_dinero(self.mes(maximo)) + " al mes, $"
                    + fmt_dinero(self.dia(maximo)) + " al día)")
        msg += "."
        return msg

    # ---------- cambios (devuelven None si salió bien, o el texto del error) ----------
    def poner_salario(self, valor):
        if valor < 0:
            return "El salario no puede ser negativo."
        self.salario = valor
        return None

    def poner_pct(self, i, valor):
        if valor < 0:
            return "El valor no puede ser negativo."
        maximo = self.maximo_pct(i)
        if valor > maximo + TOLERANCIA:
            return self._sin_espacio(self.categorias[i]["nombre"], maximo)
        self.categorias[i]["pct"] = min(valor, maximo)
        return None

    def poner_mes(self, i, monto):
        if monto < 0:
            return "El valor no puede ser negativo."
        if self.salario <= 0:
            return "Primero escribe tu salario para poder editar por dinero."
        return self.poner_pct(i, monto / self.salario * 100.0)

    def poner_dia(self, i, monto):
        return self.poner_mes(i, monto * DIAS_MES)

    def mover_frontera(self, idx, lado, angulo):
        """Modo ADAPTATIVO: arrastra el borde 'start' o 'end' de la
        categoría idx a un nuevo ángulo (0-360). Reparte el porcentaje
        entre esa categoría y lo que tenga pegado a ese lado (otra
        categoría, un hueco, o el espacio libre final)."""
        n = len(self.categorias)
        if idx < 0 or idx >= n:
            return
        if lado == "start":
            if idx <= 0:
                return  # el borde inicial de la primera categoría está fijo
            b_prev = self.frontera(idx - 1)
            b_next = self.frontera(idx + 1)
            angulo = _mas_cercano(angulo, self.frontera(idx))
            angulo = max(b_prev, min(angulo, b_next))
            self.categorias[idx - 1]["pct"] = max(0.0, round((angulo - b_prev) / 3.6, 3))
            self.categorias[idx]["pct"] = max(0.0, round((b_next - angulo) / 3.6, 3))
        else:
            b_this = self.frontera(idx)
            angulo = _mas_cercano(angulo, self.frontera(idx + 1))
            if idx >= n - 1:
                angulo = max(b_this, min(angulo, 360.0))
                self.categorias[idx]["pct"] = max(0.0, round((angulo - b_this) / 3.6, 3))
            else:
                b_next2 = self.frontera(idx + 2)
                angulo = max(b_this, min(angulo, b_next2))
                self.categorias[idx]["pct"] = max(0.0, round((angulo - b_this) / 3.6, 3))
                self.categorias[idx + 1]["pct"] = max(0.0, round((b_next2 - angulo) / 3.6, 3))

    def mover_frontera_individual(self, idx, lado, angulo):
        """Modo INDIVIDUAL: arrastra el borde 'start' o 'end' de la
        categoría idx SIN mover a sus vecinas. Si encoges, se crea (o
        crece) un hueco justo en el espacio que sueltas. Si agrandas,
        solo puedes comerte un hueco que ya esté pegado a ese lado; no
        puedes invadir a otra categoría (el punto simplemente no avanza
        más). Esto también aplica a la PRIMERA categoría: si encoges su
        borde de inicio, se crea un hueco antes de ella (empieza a
        contarse desde ahí, en vez de siempre desde arriba). Devuelve el
        índice de la categoría arrastrada (puede subir en 1 si se
        insertó un hueco ANTES de ella, al encoger por la izquierda)."""
        n = len(self.categorias)
        if idx < 0 or idx >= n:
            return idx
        segs = self.categorias

        if lado == "end":
            b_this = self.frontera(idx)
            if idx >= n - 1:
                limite_max = 360.0
            elif segs[idx + 1].get("hueco"):
                limite_max = self.frontera(idx + 2)
            else:
                limite_max = self.frontera(idx + 1)
            angulo = _mas_cercano(angulo, self.frontera(idx + 1))
            angulo = max(b_this, min(angulo, limite_max))
            antiguo = segs[idx]["pct"]
            nuevo = max(0.0, round((angulo - b_this) / 3.6, 3))
            segs[idx]["pct"] = nuevo
            diferencia = antiguo - nuevo
            if idx >= n - 1:
                pass  # el espacio libre final absorbe/da solo (es implícito)
            elif segs[idx + 1].get("hueco"):
                segs[idx + 1]["pct"] = max(0.0, round(segs[idx + 1]["pct"] + diferencia, 3))
            elif diferencia > TOLERANCIA:
                segs.insert(idx + 1, {"nombre": None, "hueco": True,
                                      "pct": round(diferencia, 3)})
            return idx

        else:  # "start"
            b_end = self.frontera(idx + 1)
            hay_prev_hueco = idx > 0 and segs[idx - 1].get("hueco")
            limite_min = self.frontera(idx - 1) if hay_prev_hueco else self.frontera(idx)
            angulo = _mas_cercano(angulo, self.frontera(idx))
            angulo = max(limite_min, min(angulo, b_end))
            antiguo = segs[idx]["pct"]
            nuevo = max(0.0, round((b_end - angulo) / 3.6, 3))
            segs[idx]["pct"] = nuevo
            diferencia = antiguo - nuevo
            if hay_prev_hueco:
                segs[idx - 1]["pct"] = max(0.0, round(segs[idx - 1]["pct"] + diferencia, 3))
                return idx
            elif diferencia > TOLERANCIA:
                # idx==0 no tiene vecino antes: se crea un hueco nuevo en su
                # lugar y la categoría pasa a la posición idx+1 (por eso el
                # punto SÍ se mueve al arrastrarlo, aunque sea la primera).
                segs.insert(idx, {"nombre": None, "hueco": True,
                                  "pct": round(diferencia, 3)})
                return idx + 1
            return idx

    def limpiar_huecos(self, mantener_idx=None):
        """Quita los huecos que quedaron en ~0% (se llenaron por completo
        al arrastrar de vuelta). Si mantener_idx es un índice a conservar
        (p. ej. la categoría seleccionada), devuelve su índice ya
        corregido según lo que se haya borrado antes de él."""
        nuevos = []
        nuevo_mantener = mantener_idx
        for j, c in enumerate(self.categorias):
            if c.get("hueco") and c["pct"] <= TOLERANCIA:
                if mantener_idx is not None and j < mantener_idx:
                    nuevo_mantener -= 1
                continue
            nuevos.append(c)
        self.categorias = nuevos
        return nuevo_mantener

    def agregar(self, nombre, pct):
        """Añade una categoría nueva AL FINAL (usado por '+ Añadir
        categoría' y al tocar el espacio gris final del gráfico)."""
        nombre = nombre.strip()
        if not nombre:
            return "Ponle un nombre a la categoría."
        if pct < 0:
            return "El valor no puede ser negativo."
        maximo = self.maximo_pct(None)
        if pct > maximo + TOLERANCIA:
            return self._sin_espacio(nombre, maximo)
        self.categorias.append({"nombre": nombre, "pct": min(pct, maximo),
                                "col": self.siguiente_color})
        self.siguiente_color += 1
        return None

    def llenar_hueco(self, i, nombre):
        """Convierte el hueco en el índice i en una categoría real nueva,
        con el mismo porcentaje que ya tenía el hueco (usado al tocar un
        hueco EN MEDIO del gráfico)."""
        nombre = nombre.strip()
        if not nombre:
            return "Ponle un nombre a la categoría."
        if i < 0 or i >= len(self.categorias) or not self.categorias[i].get("hueco"):
            return "Ese espacio ya no existe."
        self.categorias[i] = {"nombre": nombre, "pct": self.categorias[i]["pct"],
                              "col": self.siguiente_color}
        self.siguiente_color += 1
        return None

    def eliminar(self, i):
        del self.categorias[i]

    # ---------- guardar / cargar ----------
    def guardar(self, ruta):
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump({"salario": self.salario, "categorias": self.categorias},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("No se pudo guardar:", e)

    def cargar(self, ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
            salario = float(datos["salario"])
            cats = []
            for c in datos["categorias"]:
                if c.get("hueco"):
                    cats.append({"nombre": None, "hueco": True,
                                "pct": float(c["pct"])})
                else:
                    cats.append({"nombre": str(c["nombre"]), "pct": float(c["pct"]),
                                "col": int(c["col"]) if "col" in c else len(cats)})
            reales_ok = all(c["pct"] >= 0 for c in cats)
            suma_reales = sum(c["pct"] for c in cats if not c.get("hueco"))
            if salario >= 0 and reales_ok and suma_reales <= 100.0 + TOLERANCIA:
                self.salario = salario
                self.categorias = cats
                cols = [c["col"] for c in cats if not c.get("hueco")]
                self.siguiente_color = (max(cols) + 1) if cols else 0
        except Exception:
            pass  # primera vez o archivo dañado: se usan los valores por defecto


# ============================================================
#  PARTE 2: INTERFAZ (Kivy)
# ============================================================

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import escape_markup

FONDO = (0.07, 0.08, 0.11, 1)
TARJETA = (0.13, 0.15, 0.21, 1)
CAMPO = (0.20, 0.23, 0.32, 1)
AZUL = (0.25, 0.47, 0.85, 1)
MORADO = (0.56, 0.38, 0.80, 1)
ROJO = (0.78, 0.27, 0.27, 1)
GRIS = (0.35, 0.37, 0.43, 1)
BLANCO = (1, 1, 1, 1)
TEXTO_SUAVE = (0.65, 0.68, 0.75, 1)
AMARILLO = (1.0, 0.85, 0.40, 1)
COLORES = [
    (0.30, 0.55, 0.90, 1),
    (0.91, 0.36, 0.36, 1),
    (0.30, 0.69, 0.47, 1),
    (0.95, 0.65, 0.20, 1),
    (0.66, 0.42, 0.85, 1),
    (0.20, 0.72, 0.75, 1),
    (0.90, 0.45, 0.70, 1),
    (0.60, 0.70, 0.25, 1),
]


def color_de(i):
    return COLORES[i % len(COLORES)]


def resaltar(color):
    """Versión más clara de un color, para marcar la porción seleccionada."""
    r, g, b, a = color
    return (min(1.0, r + 0.28), min(1.0, g + 0.28), min(1.0, b + 0.28), a)


# ---------- pequeñas ayudas para crear widgets ----------
def boton(texto, color=AZUL, **kw):
    return Button(text=texto, font_size=sp(15), background_normal="",
                  background_down="", background_color=color, **kw)


def texto_izq(texto, tam=15, color=BLANCO, **kw):
    lbl = Label(text=texto, font_size=sp(tam), color=color, markup=True,
                halign="left", valign="middle", **kw)
    lbl.bind(size=lambda inst, s: setattr(inst, "text_size", s))
    return lbl


def _seleccionar_todo(ti, foco):
    if foco:
        Clock.schedule_once(lambda dt: ti.select_all(), 0.15)


def entrada(texto="", **kw):
    ti = TextInput(text=texto, multiline=False, font_size=sp(16),
                   background_normal="", background_active="",
                   background_color=CAMPO, foreground_color=BLANCO,
                   cursor_color=BLANCO, hint_text_color=(1, 1, 1, 0.4),
                   padding=[dp(10), dp(12), dp(10), dp(12)],
                   write_tab=False, **kw)
    ti.bind(focus=_seleccionar_todo)
    return ti


def _poner(ti, texto):
    """Cambia el texto de un campo, salvo que la persona lo esté escribiendo."""
    if not ti.focus:
        ti.text = texto


class Tarjeta(BoxLayout):
    """BoxLayout con fondo redondeado."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*TARJETA)
            self._fondo = RoundedRectangle(pos=self.pos, size=self.size,
                                           radius=[dp(12)])
        self.bind(pos=self._actualizar, size=self._actualizar)

    def _actualizar(self, *args):
        self._fondo.pos = self.pos
        self._fondo.size = self.size


class Chip(Widget):
    """Franja de color que identifica a una categoría."""

    def __init__(self, color, **kw):
        super().__init__(**kw)
        with self.canvas:
            Color(*color)
            self._r = RoundedRectangle(pos=self.pos, size=self.size,
                                       radius=[dp(4)])
        self.bind(pos=self._actualizar, size=self._actualizar)

    def _actualizar(self, *args):
        self._r.pos = self.pos
        self._r.size = self.size


RADIO_FRAC = 0.94       # el círculo ocupa el 94% del lado más corto del widget
UMBRAL_ETIQUETA = 8.0   # % mínimo para mostrar el nombre dentro de la porción
RADIO_PUNTO_VISUAL = dp(14)   # radio del punto tal como se DIBUJA (~5mm de diámetro)
RADIO_PUNTO_TOQUE = dp(32)    # radio real para AGARRARLO con el dedo (~13mm de diámetro,
                              # bastante más grande que el punto dibujado a propósito)


class Pastel(Widget):
    """
    Gráfico circular interactivo.

    Los gráficos (colores, porciones, borde, puntos) se crean UNA SOLA VEZ
    y luego solo se les cambian sus propiedades (ángulos, posición, color,
    texto). Antes se recreaban por completo en cada cambio, lo que con el
    tiempo dejaba textos "fantasma" duplicados en pantalla; con este
    esquema eso ya no puede pasar.

    - Un toque sobre una porción la selecciona: aparecen 1 o 2 puntos
      blancos en sus bordes (la primera categoría solo tiene punto al
      final, porque su inicio siempre es la parte de arriba del círculo).
    - self.modo_individual controla cómo se comporta el arrastre:
        False (adaptativo) -> la vecina que comparte el borde cede/recibe.
        True  (individual)  -> la vecina no se mueve; se abre/cierra un
                               hueco gris justo donde arrastras.
    - Un toque sobre el área gris (al final o un hueco en medio) muestra
      un botón "+" que, al tocarlo, pide solo un nombre y crea una
      categoría con TODO ese espacio.

    La app conecta on_cambio (se llama mientras se arrastra, para refrescar
    los números), on_soltar (al terminar de arrastrar, para guardar) y
    on_espacio_vacio(indice_hueco, pct) (al pedir crear una categoría).
    """

    def __init__(self, presupuesto, **kw):
        super().__init__(**kw)
        self.p = presupuesto
        self.vista = None              # ScrollView contenedor
        self.modo_individual = False
        self.on_cambio = lambda: None
        self.on_soltar = lambda: None
        self.on_espacio_vacio = lambda indice_hueco, pct: None
        self.editable = True           # la app lo pone en False fuera de "Editar porcentajes"

        self.seleccionado = None       # índice de la categoría seleccionada
                                        # (self._fijar_seleccion() lo cambia de acá en más)
        self._arrastre = None          # (idx, "start"/"end") mientras se arrastra
        self._radio = dp(1)
        self._boton_mas = None

        self._piezas = []              # [{"color":Color,"ellipse":Ellipse,"label":Label}]
        self._gap_color = None
        self._gap_ellipse = None
        self._borde = None
        self._handle_ini = None
        self._handle_fin = None
        self._handle_ini_borde = None
        self._handle_fin_borde = None

        self.bind(pos=self.posicionar, size=self.posicionar)

    # ---------------------------------------------------------------
    # construir / actualizar los gráficos
    # ---------------------------------------------------------------
    def reconstruir(self, *args):
        """Recrea todos los objetos gráficos. Solo hace falta cuando cambia
        el NÚMERO de segmentos (categorías o huecos); actualizar() lo
        detecta solo y llama aquí cuando corresponde."""
        self.canvas.before.clear()
        self.canvas.after.clear()
        self.clear_widgets()
        self._piezas = []
        self._fijar_seleccion(None)
        self._boton_mas = None

        n = len(self.p.categorias)
        colores, elipses = [], []
        with self.canvas.before:
            for i in range(n):
                colores.append(Color(1, 1, 1, 1))   # el color real se pone en actualizar()
                elipses.append(Ellipse(angle_start=0, angle_end=0))
            self._gap_color = Color(*GRIS)
            self._gap_ellipse = Ellipse(angle_start=0, angle_end=0)
            Color(1, 1, 1, 0.9)
            self._borde = Line(circle=(0, 0, 1), width=dp(1.5))

        # los Label se crean FUERA del "with canvas" de arriba a propósito:
        # crear widgets con canvas mientras el canvas del padre está
        # "activo" es justo lo que causaba los textos fantasma.
        for i in range(n):
            lbl = Label(font_size=sp(13), bold=True, halign="center",
                        valign="middle", size_hint=(None, None),
                        size=(dp(92), dp(46)), text_size=(dp(92), dp(46)))
            self.add_widget(lbl)
            self._piezas.append({"color": colores[i], "ellipse": elipses[i],
                                 "label": lbl})

        with self.canvas.after:
            Color(1, 1, 1, 1)
            self._handle_ini = Ellipse(size=(0, 0))
            Color(0.1, 0.1, 0.15, 1)
            self._handle_ini_borde = Line(circle=(0, 0, 0), width=dp(1.3))
            Color(1, 1, 1, 1)
            self._handle_fin = Ellipse(size=(0, 0))
            Color(0.1, 0.1, 0.15, 1)
            self._handle_fin_borde = Line(circle=(0, 0, 0), width=dp(1.3))

        self.actualizar()

    def actualizar(self, *args):
        """Actualiza ángulos y textos según los datos actuales. No crea ni
        destruye nada -> seguro para llamarlo en cada cambio, incluso
        mientras se arrastra un punto."""
        if len(self._piezas) != len(self.p.categorias):
            self.reconstruir()
            return
        angulo = 0.0
        for i, c in enumerate(self.p.categorias):
            pct = c["pct"]
            fin = min(angulo + pct * 3.6, 360.0)
            pieza = self._piezas[i]
            pieza["ellipse"].angle_start = angulo
            pieza["ellipse"].angle_end = fin
            es_hueco = c.get("hueco", False)
            if (not es_hueco) and pct >= UMBRAL_ETIQUETA:
                nombre = c["nombre"]
                corto = nombre if len(nombre) <= 12 else nombre[:11] + "."
                pieza["label"].text = corto + "\n" + fmt_pct(pct) + "%"
                pieza["label"].opacity = 1
            else:
                pieza["label"].text = ""
                pieza["label"].opacity = 0
            angulo = fin
        if self.p.espacio_final() > 0:
            self._gap_color.rgba = GRIS
            self._gap_ellipse.angle_start = angulo
            self._gap_ellipse.angle_end = 360.0
        else:
            self._gap_color.rgba = (0, 0, 0, 0)
        self.posicionar()

    def posicionar(self, *args):
        """Recoloca todo según la posición/tamaño actuales del widget."""
        d = min(self.width, self.height) * RADIO_FRAC
        r = d / 2.0
        self._radio = max(r, dp(1))
        if r <= 0:
            return
        cx, cy = self.center
        caja = (cx - r, cy - r)
        for pieza in self._piezas:
            pieza["ellipse"].pos = caja
            pieza["ellipse"].size = (d, d)
        if self._gap_ellipse is not None:
            self._gap_ellipse.pos = caja
            self._gap_ellipse.size = (d, d)
        if self._borde is not None:
            self._borde.circle = (cx, cy, r)

        for i, c in enumerate(self.p.categorias):
            if i >= len(self._piezas) or c.get("hueco") or c["pct"] < UMBRAL_ETIQUETA:
                continue
            medio = (self.p.frontera(i) + self.p.frontera(i + 1)) / 2.0
            rad = math.radians(medio)
            f = 0.0 if c["pct"] >= 99.5 else 0.6
            self._piezas[i]["label"].center = (cx + f * r * math.sin(rad),
                                               cy + f * r * math.cos(rad))
        self._posicionar_manijas()
        self._quitar_boton_mas()

    def _fijar_seleccion(self, idx):
        """Cambia self.seleccionado y, de paso, apaga o prende el scroll
        de la pantalla. Importante: el scroll se apaga ACÁ, apenas se
        selecciona una categoría (aparecen sus puntos) -- no recién
        cuando ya se logró agarrar un punto. Si no, el primer intento de
        arrastre rápido (tocar y mover el dedo de una) corre el riesgo de
        que la pantalla lo interprete como "querés scrollear" antes de
        que a este widget le llegue siquiera el toque (es un mecanismo
        del propio ScrollView: si el dedo viaja cierta distancia dentro
        de los primeros ~55ms, se lo queda él; recién si te quedás
        quieto ese ratito te lo pasa a este widget). Con el scroll ya
        apagado desde que seleccionás, ese problema no llega a pasar."""
        self.seleccionado = idx
        if self.vista is not None:
            self.vista.do_scroll_y = (idx is None)

    def _punto_borde(self, angulo_grados):
        cx, cy = self.center
        rad = math.radians(angulo_grados)
        return (cx + self._radio * math.sin(rad), cy + self._radio * math.cos(rad))

    def _posicionar_manijas(self):
        if self._handle_ini is None:
            return
        # colores base de todas las porciones + resaltado de la seleccionada
        for i, pieza in enumerate(self._piezas):
            if i >= len(self.p.categorias):
                continue
            c = self.p.categorias[i]
            base = GRIS if c.get("hueco") else color_de(c.get("col", i))
            pieza["color"].rgba = resaltar(base) if i == self.seleccionado else base

        d = RADIO_PUNTO_VISUAL * 2
        if self.seleccionado is None or self.seleccionado >= len(self.p.categorias):
            self._handle_ini.size = (0, 0)
            self._handle_fin.size = (0, 0)
            self._handle_ini_borde.circle = (0, 0, 0)
            self._handle_fin_borde.circle = (0, 0, 0)
            return

        i = self.seleccionado
        b0, b1 = self.p.frontera(i), self.p.frontera(i + 1)
        x, y = self._punto_borde(b0)
        self._handle_ini.pos = (x - d / 2, y - d / 2)
        self._handle_ini.size = (d, d)
        self._handle_ini_borde.circle = (x, y, d / 2)

        x, y = self._punto_borde(b1)
        self._handle_fin.pos = (x - d / 2, y - d / 2)
        self._handle_fin.size = (d, d)
        self._handle_fin_borde.circle = (x, y, d / 2)

    # ---------------------------------------------------------------
    # toques
    # ---------------------------------------------------------------
    def _segmento_en(self, angulo):
        """Índice del segmento (categoría o hueco) bajo ese ángulo, o None
        si cae en el espacio libre final (después del último segmento)."""
        acumulado = 0.0
        for i, c in enumerate(self.p.categorias):
            fin = acumulado + c["pct"] * 3.6
            if acumulado <= angulo < fin:
                return i
            acumulado = fin
        return None

    def on_touch_down(self, touch):
        if not self.editable:
            return False
        if not self.collide_point(*touch.pos):
            return False
        if super().on_touch_down(touch):
            return True  # el botón "+" (si estaba visible) ya lo manejó

        # ¿tocó uno de los puntos de la categoría ya seleccionada? Esto se
        # revisa PRIMERO y con un radio generoso e independiente de si el
        # dedo cayó un poco afuera del círculo principal (el punto sobresale
        # justo ahí, en el borde). Si los dos puntos están cerca, gana el
        # más cercano al dedo, para no tener que acertarle "al pixel".
        if self.seleccionado is not None and self.seleccionado < len(self.p.categorias):
            i = self.seleccionado
            b0, b1 = self.p.frontera(i), self.p.frontera(i + 1)
            x0, y0 = self._punto_borde(b0)
            x1, y1 = self._punto_borde(b1)
            d0 = math.hypot(touch.x - x0, touch.y - y0)
            d1 = math.hypot(touch.x - x1, touch.y - y1)
            if min(d0, d1) <= RADIO_PUNTO_TOQUE:
                self._empezar_arrastre(touch, i, "start" if d0 <= d1 else "end")
                return True

        cx, cy = self.center
        dx, dy = touch.x - cx, touch.y - cy
        dist = math.hypot(dx, dy)
        if dist > self._radio * 1.15:
            self._quitar_boton_mas()
            self._fijar_seleccion(None)
            self._posicionar_manijas()
            return True

        self._quitar_boton_mas()
        angulo = math.degrees(math.atan2(dx, dy)) % 360.0
        idx = self._segmento_en(angulo)
        if idx is None:
            self._fijar_seleccion(None)
            self._mostrar_boton_mas(touch.pos, None)
        elif self.p.categorias[idx].get("hueco"):
            self._fijar_seleccion(None)
            self._mostrar_boton_mas(touch.pos, idx)
        elif idx == self.seleccionado:
            self._fijar_seleccion(None)
        else:
            self._fijar_seleccion(idx)
        self._posicionar_manijas()
        return True

    def _empezar_arrastre(self, touch, idx, lado):
        touch.grab(self)
        self._arrastre = (idx, lado)
        if self.vista is not None:
            self.vista.do_scroll_y = False

    def on_touch_move(self, touch):
        if touch.grab_current is not self or self._arrastre is None:
            return super().on_touch_move(touch)
        idx, lado = self._arrastre
        cx, cy = self.center
        angulo = math.degrees(math.atan2(touch.x - cx, touch.y - cy)) % 360.0
        # el punto de inicio de la primera categoría no tiene ninguna vecina
        # antes con quien repartir, así que siempre se comporta "individual"
        # (deja un hueco), sin importar el modo elegido.
        forzar_individual = (idx == 0 and lado == "start")
        if self.modo_individual or forzar_individual:
            nuevo_idx = self.p.mover_frontera_individual(idx, lado, angulo)
            if nuevo_idx != idx:
                self._arrastre = (nuevo_idx, lado)
                self._fijar_seleccion(nuevo_idx)
        else:
            self.p.mover_frontera(idx, lado, angulo)
        self.on_cambio()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._arrastre = None
            if self.vista is not None:
                self.vista.do_scroll_y = True
            self._fijar_seleccion(self.p.limpiar_huecos(self.seleccionado))
            self.on_soltar()
            return True
        return super().on_touch_up(touch)

    # ---------------------------------------------------------------
    # botón "+" sobre el espacio vacío
    # ---------------------------------------------------------------
    def _quitar_boton_mas(self):
        if self._boton_mas is not None:
            self.remove_widget(self._boton_mas)
            self._boton_mas = None

    def _mostrar_boton_mas(self, pos, indice_hueco):
        pct = (self.p.espacio_final() if indice_hueco is None
              else self.p.categorias[indice_hueco]["pct"])
        if pct <= 0:
            return
        hay_categorias_reales = any(not c.get("hueco") for c in self.p.categorias)
        if indice_hueco is None and not hay_categorias_reales:
            # si el círculo está 100% vacío, no lo llenes entero: así la
            # primera categoría queda con sus dos puntos en lugares
            # distintos (en 100% ambos puntos caerían en el mismo sitio).
            pct = min(pct, 50.0)
        b = Button(text="+", font_size=sp(24), bold=True,
                  background_normal="", background_color=AMARILLO,
                  color=(0.1, 0.1, 0.1, 1), size_hint=(None, None),
                  size=(dp(50), dp(50)))
        b.center = pos
        b.bind(on_release=lambda *a: self._pedir_categoria_nueva(indice_hueco, pct))
        self.add_widget(b)
        self._boton_mas = b

    def _pedir_categoria_nueva(self, indice_hueco, pct):
        self._quitar_boton_mas()
        self.on_espacio_vacio(indice_hueco, pct)


class PresupuestoApp(App):
    title = "Presupuesto"

    # ---------- arranque ----------
    def ruta_datos(self):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            if os.access(base, os.W_OK):
                return os.path.join(base, ARCHIVO)
        except Exception:
            pass
        return os.path.join(self.user_data_dir, ARCHIVO)

    def build(self):
        Window.clearcolor = FONDO
        try:
            Window.softinput_mode = "below_target"   # sube la pantalla al abrir el teclado
        except Exception:
            pass

        self.p = Presupuesto()
        self.ruta = self.ruta_datos()
        self.p.cargar(self.ruta)
        self.modo_edicion = False
        self._refrescos = []

        self.raiz = ScrollView(do_scroll_x=False, bar_width=dp(4))
        self.contenido = BoxLayout(orientation="vertical", size_hint_y=None,
                                   padding=[dp(14), dp(30), dp(14), dp(14)],
                                   spacing=dp(12))
        self.contenido.bind(minimum_height=self.contenido.setter("height"))
        self.raiz.add_widget(self.contenido)
        self.armar_pantalla()
        return self.raiz

    def on_pause(self):
        self.p.guardar(self.ruta)
        return True

    def on_stop(self):
        self.p.guardar(self.ruta)

    # ---------- pantalla principal ----------
    def armar_pantalla(self):
        c = self.contenido
        c.clear_widgets()

        c.add_widget(texto_izq("Mi presupuesto", 24, bold=True,
                               size_hint_y=None, height=dp(40)))

        self.pastel = Pastel(self.p, size_hint_y=None, height=dp(290))
        self.pastel.vista = self.raiz
        self.pastel.editable = self.modo_edicion
        self.pastel.on_cambio = self.actualizar_valores
        self.pastel.on_soltar = self._al_soltar_arrastre
        self.pastel.on_espacio_vacio = self.abrir_agregar_rapido
        c.add_widget(self.pastel)

        c.add_widget(texto_izq(
            "Con 'Editar porcentajes' activo: toca una porción para "
            "arrastrar sus puntos, o toca el espacio gris para crear "
            "una categoría ahí.", 12,
            color=TEXTO_SUAVE, size_hint_y=None, height=dp(40)))

        self.btn_modo = boton("Modo: las vecinas se ajustan", color=AZUL,
                              size_hint_y=None, height=dp(44))
        self.btn_modo.bind(on_release=self.alternar_modo_arrastre)
        c.add_widget(self.btn_modo)

        fila = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        self.btn_editar = boton("Editar porcentajes")
        self.btn_editar.bind(on_release=self.alternar_edicion)
        btn_agregar = boton("+ Añadir categoría", color=GRIS)
        btn_agregar.bind(on_release=self.abrir_agregar)
        fila.add_widget(self.btn_editar)
        fila.add_widget(btn_agregar)
        c.add_widget(fila)

        self.lbl_libre = texto_izq("", 14, color=AMARILLO,
                                   size_hint_y=None, height=dp(28))
        c.add_widget(self.lbl_libre)

        # ----- caja "información financiera" -----
        caja = Tarjeta(orientation="vertical", size_hint_y=None,
                       padding=dp(12), spacing=dp(10))
        caja.bind(minimum_height=caja.setter("height"))

        titulo = Label(text="Información financiera", font_size=sp(20),
                       bold=True, size_hint_y=None, height=dp(34))
        caja.add_widget(titulo)

        fila_sal = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        fila_sal.add_widget(texto_izq("Salario neto: $", 17, size_hint_x=0.55))
        self.in_salario = entrada(fmt_dinero(self.p.salario))
        self.in_salario.bind(on_text_validate=self.confirmar_salario)
        self.in_salario.bind(
            focus=lambda inst, f: None if f else self.confirmar_salario(inst))
        fila_sal.add_widget(self.in_salario)
        caja.add_widget(fila_sal)

        self.lbl_ayuda = texto_izq("", 13, color=TEXTO_SUAVE,
                                   size_hint_y=None, height=dp(40))
        caja.add_widget(self.lbl_ayuda)

        self.contenedor_cats = BoxLayout(orientation="vertical",
                                         size_hint_y=None, spacing=dp(10))
        self.contenedor_cats.bind(
            minimum_height=self.contenedor_cats.setter("height"))
        caja.add_widget(self.contenedor_cats)
        c.add_widget(caja)

        # espacio extra al final para que el teclado no tape los campos
        c.add_widget(Widget(size_hint_y=None, height=dp(280)))

        self.reconstruir_categorias()

    # ---------- tarjetas de categorías ----------
    def reconstruir_categorias(self):
        """Vuelve a crear las tarjetas (al añadir/borrar o cambiar de modo).
        Los huecos NUNCA se muestran como tarjeta, solo en el gráfico."""
        self.contenedor_cats.clear_widgets()
        self._refrescos = []
        if self.modo_edicion:
            self.lbl_ayuda.text = ("Cambia el %, el dinero al mes o al día: "
                                   "los otros valores se ajustan solos.")
        else:
            self.lbl_ayuda.text = "Toca 'Editar porcentajes' para cambiar el reparto."
        hay_categorias = any(not c.get("hueco") for c in self.p.categorias)
        if not hay_categorias:
            self.contenedor_cats.add_widget(
                texto_izq("No hay categorías. Toca '+ Añadir categoría'.", 15,
                          color=TEXTO_SUAVE, size_hint_y=None, height=dp(40)))
        for i, c in enumerate(self.p.categorias):
            if c.get("hueco"):
                continue
            if self.modo_edicion:
                self.contenedor_cats.add_widget(self.tarjeta_edicion(i))
            else:
                self.contenedor_cats.add_widget(self.tarjeta_lectura(i))
        self.actualizar_valores()

    def tarjeta_lectura(self, i):
        t = Tarjeta(orientation="horizontal", size_hint_y=None, height=dp(70),
                    padding=dp(10), spacing=dp(10))
        col = self.p.categorias[i].get("col", i)
        t.add_widget(Chip(color_de(col), size_hint=(None, 1), width=dp(8)))
        lbl = texto_izq("", 16)
        t.add_widget(lbl)

        def refrescar():
            if i >= len(self.p.categorias) or self.p.categorias[i].get("hueco"):
                return
            cat = self.p.categorias[i]
            pct = cat["pct"]
            nombre = escape_markup(cat["nombre"])
            lbl.text = ("[b]" + nombre + "[/b]   " + fmt_pct(pct) + "%\n"
                        + "Mes: $" + fmt_dinero(self.p.mes(pct))
                        + "      Día: $" + fmt_dinero(self.p.dia(pct)))

        self._refrescos.append(refrescar)
        return t

    def tarjeta_edicion(self, i):
        cat = self.p.categorias[i]
        col = cat.get("col", i)
        t = Tarjeta(orientation="vertical", size_hint_y=None, height=dp(142),
                    padding=dp(10), spacing=dp(8))

        fila1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        fila1.add_widget(Chip(color_de(col), size_hint=(None, 1), width=dp(8)))
        in_nombre = entrada(cat["nombre"])
        in_nombre.bind(
            on_text_validate=lambda inst, i=i: self.confirmar_nombre(i, inst))
        in_nombre.bind(
            focus=lambda inst, f, i=i: None if f else self.confirmar_nombre(i, inst))
        fila1.add_widget(in_nombre)
        b_borrar = boton("Borrar", color=ROJO, size_hint_x=None, width=dp(80))
        b_borrar.bind(on_release=lambda *a, i=i: self.pedir_borrar(i))
        fila1.add_widget(b_borrar)
        t.add_widget(fila1)

        fila2 = BoxLayout(size_hint_y=None, height=dp(66), spacing=dp(8))
        campos = {}
        for clave, titulo in (("pct", "Porcentaje %"),
                              ("mes", "Al mes $"),
                              ("dia", "Al día $")):
            colc = BoxLayout(orientation="vertical", spacing=dp(2))
            colc.add_widget(texto_izq(titulo, 12, color=TEXTO_SUAVE,
                                      size_hint_y=None, height=dp(18)))
            ti = entrada("")
            self.enlazar(ti, clave, i)
            colc.add_widget(ti)
            fila2.add_widget(colc)
            campos[clave] = ti
        t.add_widget(fila2)

        def refrescar():
            if i >= len(self.p.categorias) or self.p.categorias[i].get("hueco"):
                return
            pct = self.p.categorias[i]["pct"]
            _poner(campos["pct"], fmt_pct(pct))
            _poner(campos["mes"], fmt_dinero(self.p.mes(pct)))
            _poner(campos["dia"], fmt_dinero(self.p.dia(pct)))

        self._refrescos.append(refrescar)
        return t

    def enlazar(self, ti, clave, i):
        ti.bind(on_text_validate=lambda inst: self.confirmar(clave, i, inst))
        ti.bind(focus=lambda inst, f: None if f else self.confirmar(clave, i, inst))

    # ---------- actualizar lo que se ve ----------
    def actualizar_valores(self):
        for f in self._refrescos:
            f()
        self.pastel.actualizar()
        libre = self.p.libre_pct()
        if libre > 0:
            self.lbl_libre.text = ("Sin asignar: " + fmt_pct(libre) + "%  ($"
                                   + fmt_dinero(self.p.mes(libre)) + " al mes)")
            self.lbl_libre.color = AMARILLO
        else:
            self.lbl_libre.text = "Todo tu salario está repartido (100%)"
            self.lbl_libre.color = TEXTO_SUAVE

    def _al_soltar_arrastre(self):
        self.p.guardar(self.ruta)
        # el número de segmentos pudo cambiar (se creó o se limpió un hueco)
        if len(self._refrescos) != sum(1 for c in self.p.categorias
                                       if not c.get("hueco")):
            self.reconstruir_categorias()
        else:
            self.actualizar_valores()

    # ---------- confirmar ediciones ----------
    def confirmar(self, clave, i, ti):
        """Se llama al pulsar Enter o al salir del campo."""
        if i >= len(self.p.categorias):
            return
        pct_actual = self.p.categorias[i]["pct"]
        if clave == "pct":
            actual, fmt = pct_actual, fmt_pct
        elif clave == "mes":
            actual, fmt = self.p.mes(pct_actual), fmt_dinero
        else:
            actual, fmt = self.p.dia(pct_actual), fmt_dinero

        try:
            nuevo = a_numero(ti.text)
        except ValueError as e:
            ti.text = fmt(actual)
            self.mostrar_error(str(e))
            return

        if abs(nuevo - round(actual, 2)) < 1e-9:
            self.actualizar_valores()      # no cambió nada: solo normaliza el texto
            return

        if clave == "pct":
            err = self.p.poner_pct(i, nuevo)
        elif clave == "mes":
            err = self.p.poner_mes(i, nuevo)
        else:
            err = self.p.poner_dia(i, nuevo)

        if err:
            ti.text = fmt(actual)
            self.mostrar_error(err)
        else:
            self.p.guardar(self.ruta)
        self.actualizar_valores()

    def confirmar_nombre(self, i, ti):
        if i >= len(self.p.categorias):
            return
        actual = self.p.categorias[i]["nombre"]
        nuevo = ti.text.strip()
        if not nuevo:
            ti.text = actual
            return
        if nuevo != actual:
            self.p.categorias[i]["nombre"] = nuevo
            self.p.guardar(self.ruta)
            self.pastel.actualizar()

    def confirmar_salario(self, ti):
        try:
            nuevo = a_numero(ti.text)
        except ValueError as e:
            ti.text = fmt_dinero(self.p.salario)
            self.mostrar_error(str(e))
            return
        if abs(nuevo - round(self.p.salario, 2)) < 1e-9:
            _poner(ti, fmt_dinero(self.p.salario))
            return
        err = self.p.poner_salario(nuevo)
        if err:
            ti.text = fmt_dinero(self.p.salario)
            self.mostrar_error(err)
        else:
            self.p.guardar(self.ruta)
            self.actualizar_valores()

    def alternar_edicion(self, *args):
        self.modo_edicion = not self.modo_edicion
        self.btn_editar.text = "Listo" if self.modo_edicion else "Editar porcentajes"
        self.pastel.editable = self.modo_edicion
        if not self.modo_edicion:
            self.pastel.seleccionado = None
            self.pastel._quitar_boton_mas()
            self.pastel._posicionar_manijas()
        self.reconstruir_categorias()

    def alternar_modo_arrastre(self, *args):
        self.pastel.modo_individual = not self.pastel.modo_individual
        if self.pastel.modo_individual:
            self.btn_modo.text = "Modo: categorías fijas (deja hueco)"
            self.btn_modo.background_color = MORADO
        else:
            self.btn_modo.text = "Modo: las vecinas se ajustan"
            self.btn_modo.background_color = AZUL

    # ---------- ventanas emergentes ----------
    def mostrar_error(self, mensaje):
        cont = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        lbl = Label(text=mensaje, font_size=sp(15), halign="center")
        lbl.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        cont.add_widget(lbl)
        b = boton("Entendido", size_hint_y=None, height=dp(46))
        cont.add_widget(b)
        popup = Popup(title="Aviso", content=cont, size_hint=(0.9, None),
                      height=dp(300))
        b.bind(on_release=popup.dismiss)
        popup.open()

    def abrir_agregar(self, *args):
        cont = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        cont.add_widget(texto_izq(
            "Porcentaje libre: " + fmt_pct(self.p.maximo_pct(None)) + "%", 14,
            color=AMARILLO, size_hint_y=None, height=dp(24)))
        in_nombre = entrada("", hint_text="Nombre (ej. Ahorro)",
                            size_hint_y=None, height=dp(44))
        in_pct = entrada("0", hint_text="Porcentaje (ej. 10)",
                         size_hint_y=None, height=dp(44))
        cont.add_widget(in_nombre)
        cont.add_widget(in_pct)
        lbl_err = Label(text="", font_size=sp(13), color=(1, 0.55, 0.55, 1),
                        halign="center", size_hint_y=None, height=dp(70))
        lbl_err.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        cont.add_widget(lbl_err)

        fila = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        b_cancelar = boton("Cancelar", color=GRIS)
        b_ok = boton("Añadir")
        fila.add_widget(b_cancelar)
        fila.add_widget(b_ok)
        cont.add_widget(fila)

        popup = Popup(title="Nueva categoría", content=cont,
                      size_hint=(0.92, None), height=dp(370), auto_dismiss=False)

        def aceptar(*a):
            try:
                valor = a_numero(in_pct.text or "0")
            except ValueError as e:
                lbl_err.text = str(e)
                return
            err = self.p.agregar(in_nombre.text, valor)
            if err:
                lbl_err.text = err
                return
            self.p.guardar(self.ruta)
            popup.dismiss()
            self.reconstruir_categorias()

        b_cancelar.bind(on_release=popup.dismiss)
        b_ok.bind(on_release=aceptar)
        popup.open()

    def abrir_agregar_rapido(self, indice_hueco, pct):
        """Crear categoría tocando el espacio vacío del gráfico (al final
        o un hueco en medio): solo pide el nombre, el porcentaje ya es
        exactamente ese espacio."""
        cont = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        cont.add_widget(texto_izq(
            "Espacio disponible: " + fmt_pct(pct) + "%\n($"
            + fmt_dinero(self.p.mes(pct)) + " al mes, $"
            + fmt_dinero(self.p.dia(pct)) + " al día)", 14,
            color=AMARILLO, size_hint_y=None, height=dp(50)))
        in_nombre = entrada("", hint_text="Nombre de la categoría",
                            size_hint_y=None, height=dp(44))
        cont.add_widget(in_nombre)
        lbl_err = Label(text="", font_size=sp(13), color=(1, 0.55, 0.55, 1),
                        halign="center", size_hint_y=None, height=dp(40))
        lbl_err.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        cont.add_widget(lbl_err)

        fila = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        b_cancelar = boton("Cancelar", color=GRIS)
        b_ok = boton("Crear categoría")
        fila.add_widget(b_cancelar)
        fila.add_widget(b_ok)
        cont.add_widget(fila)

        popup = Popup(title="Nueva categoría en el espacio libre", content=cont,
                      size_hint=(0.92, None), height=dp(340), auto_dismiss=False)

        def aceptar(*a):
            if indice_hueco is None:
                err = self.p.agregar(in_nombre.text, pct)
            else:
                err = self.p.llenar_hueco(indice_hueco, in_nombre.text)
            if err:
                lbl_err.text = err
                return
            self.p.guardar(self.ruta)
            popup.dismiss()
            self.reconstruir_categorias()

        b_cancelar.bind(on_release=popup.dismiss)
        b_ok.bind(on_release=aceptar)
        popup.open()

    def pedir_borrar(self, i):
        if i >= len(self.p.categorias):
            return
        nombre = self.p.categorias[i]["nombre"]
        cont = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        lbl = Label(text="¿Borrar '" + nombre + "'?\nSu porcentaje quedará sin asignar.",
                    font_size=sp(15), halign="center")
        lbl.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        cont.add_widget(lbl)
        fila = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        b_no = boton("Cancelar", color=GRIS)
        b_si = boton("Borrar", color=ROJO)
        fila.add_widget(b_no)
        fila.add_widget(b_si)
        cont.add_widget(fila)
        popup = Popup(title="Borrar categoría", content=cont,
                      size_hint=(0.9, None), height=dp(240), auto_dismiss=False)

        def borrar(*a):
            if i < len(self.p.categorias):
                self.p.eliminar(i)
                self.p.guardar(self.ruta)
            popup.dismiss()
            self.reconstruir_categorias()

        b_no.bind(on_release=popup.dismiss)
        b_si.bind(on_release=borrar)
        popup.open()


if __name__ == "__main__":
    PresupuestoApp().run()

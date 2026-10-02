# Buildozer exige que el archivo de arranque se llame exactamente "main.py".
# No hace falta tocar nada acá ni duplicar código: este archivo solo
# arranca la app que ya está en presupuesto.py. Seguí editando y pegando
# en Pydroid 3 ese archivo (presupuesto.py) como siempre.

from presupuesto import PresupuestoApp

if __name__ == "__main__":
    PresupuestoApp().run()

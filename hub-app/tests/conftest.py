import sys
from pathlib import Path

# Permet de lancer `pytest` depuis n'importe quel répertoire en s'assurant
# que le package `app` (hub-app/app) est importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

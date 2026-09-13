import os
import tempfile


# Isola a suite da base real do usuario antes da coleta dos modulos.
os.environ["LEMOVE_DATA_DIR"] = tempfile.mkdtemp(prefix="lemove-tests-")

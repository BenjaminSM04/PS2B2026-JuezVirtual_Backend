"""Identificadores de lenguajes del contrato, sin cargar modelos ni base de datos."""


class LanguageName:
    C = "C"
    CPP = "C++"
    JAVA = "Java"
    PYTHON3 = "Python3"
    GO = "Golang"
    JAVASCRIPT = "JavaScript"

    @classmethod
    def choices(cls):
        return (cls.C, cls.CPP, cls.JAVA, cls.PYTHON3, cls.GO, cls.JAVASCRIPT)

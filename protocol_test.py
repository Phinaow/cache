class ComplexObject:
    def __init__(self, arg1, arg2):
        self.arg1 = arg1
        self.arg2 = arg2

    def methode(self):
        print("Original")

class ComplexSurcharge(ComplexObject):
    def __new__(cls, obj_a_transformer):
        # On change la classe de l'objet existant
        obj_a_transformer.__class__ = cls
        return obj_a_transformer

    def __init__(self, *args, **kwargs):
        # On ne fait RIEN ici.
        # L'objet possède déjà arg1 et arg2 car il a été initialisé
        # lorsqu'il était encore un ComplexObject.
        pass

    def methode(self):
        print(f"Surchargé ! (Data: {self.arg1})")
        super().methode()

# --- TEST ---
obj = ComplexObject("A", "B")
new_one = ComplexSurcharge(obj) # Plus d'erreur !

new_one.methode()

print(f"Est-ce le même objet ? {obj is new_one}") # True
print(f"isinstance(new_one, ComplexObject) ? {isinstance(new_one, ComplexObject)}")

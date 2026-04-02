"""
cocotb_struct_wrapper.py
========================
Wrapper cocotb/Verilator pour accéder aux champs de structs SystemVerilog
comme s'ils étaient des signaux cocotb natifs.

Architecture
------------
- ``DutWrapper(HierarchyObject)``
    Hérite de HierarchyObject en réutilisant le handle GPI du DUT.
    Le comportement cocotb est donc 100% natif pour tous les signaux
    scalaires. Seuls les ports déclarés dans ``port_types`` sont
    interceptés pour retourner un ``StructProxy``.

- ``StructProxy``
    Représente un port struct. Expose ses champs comme des ``FieldProxy``.
    Maintient un cache partagé avec ses enfants (sous-structs imbriquées).
    ``.value`` délègue au signal cocotb sous-jacent (vecteur brut).

- ``FieldProxy``
    Représente un champ individuel (logic/enum).
    ``.value`` lit les bons bits depuis le vecteur / met en cache.
    Tout attribut inconnu est délégué au signal cocotb parent.

Le flush est déclenché par ``await w(trigger)`` ou ``w.commit()``.

Usage
-----
::

    from verible_struct_parser import parse_verible_json
    from cocotb_struct_wrapper import DutWrapper
    import cocotb
    from cocotb.triggers import RisingEdge

    @cocotb.test()
    async def my_test(dut):
        structs = parse_verible_json("pkg.json")
        w = DutWrapper(
            dut,
            structs=structs,
            port_types={"data_i": "cache_op_t"},
        )

        # Signaux scalaires : comportement HierarchyObject natif complet
        w.clk_i.value
        w.rst_ni.value = 0

        # Ports struct
        w.data_i.mem_addr.value    = 0xFF
        w.data_i.nb_transfer.value = 27
        val = w.data_i.mem_addr.value
        raw = w.data_i.value

        # Sous-structs imbriquées
        w.data_i.sub.field.value = 3

        # Flush auto + trigger
        await w(RisingEdge(dut.clk_i))

        # Flush manuel
        w.commit()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from cocotb.handle import HierarchyObject
from verible_struct_parser import StructDef, StructMember
from cocotb.triggers import RisingEdge
from cocotb import start_soon


# ---------------------------------------------------------------------------
# Calcul des offsets dans le vecteur packed
# ---------------------------------------------------------------------------

def _compute_offsets(struct_def: StructDef) -> Dict[str, int]:
    """
    Retourne { nom_membre: offset_lsb } dans le vecteur packed.

    Convention SystemVerilog packed : premier membre déclaré = bits de poids fort.
    On itère en sens inverse pour accumuler depuis le bit 0.

    Exemple — struct { logic [7:0] a; logic [3:0] b; }  (total 12 bits)
        b → offset 0   (bits  [3:0])
        a → offset 4   (bits [11:4])
    """
    offsets: Dict[str, int] = {}
    bit = 0
    for member in reversed(struct_def.members):
        if member.size < 0:
            break
        offsets[member.name] = bit
        bit += member.size
    return offsets


# ---------------------------------------------------------------------------
# FieldProxy — champ individuel (logic / enum)
# ---------------------------------------------------------------------------

class FieldProxy:
    """
    Représente un champ individuel d'un port struct.

    Imite le comportement d'un handle cocotb :
    - ``field.value``       → extrait les bits du champ depuis le vecteur DUT
    - ``field.value = v``   → met en cache (pas d'écriture immédiate)
    - ``field.driven``      → délégué au signal cocotb parent
    - ``int(field)``        → entier extrait du vecteur courant

    Paramètres
    ----------
    name          : nom du champ
    parent_signal : handle cocotb du port struct racine (ex: dut.data_i)
    cache         : dict partagé { cache_key: valeur }
    cache_key     : clé de ce champ dans le cache (ex: "data_i.mem_addr")
    offset        : position LSB du champ dans le vecteur packed
    size          : largeur en bits du champ
    """

    _RESERVED = frozenset({"_name", "_signal", "_cache", "_key", "_offset", "_size"})

    def __init__(
        self,
        name: str,
        parent_signal: Any,
        cache: Dict[str, int],
        cache_key: str,
        offset: int,
        size: int,
    ) -> None:
        object.__setattr__(self, "_name",   name)
        object.__setattr__(self, "_signal", parent_signal)
        object.__setattr__(self, "_cache",  cache)
        object.__setattr__(self, "_key",    cache_key)
        object.__setattr__(self, "_offset", offset)
        object.__setattr__(self, "_size",   size)

    # ------------------------------------------------------------------
    # .value
    # ------------------------------------------------------------------

    @property
    def value(self) -> int:
        """Extrait la valeur du champ depuis le vecteur DUT courant."""
        signal = object.__getattribute__(self, "_signal")
        offset = object.__getattribute__(self, "_offset")
        size   = object.__getattribute__(self, "_size")
        raw    = int(signal.value)
        mask   = (1 << size) - 1
        return (raw >> offset) & mask

    @value.setter
    def value(self, v: int) -> None:
        """Met la valeur en cache (flushée au prochain commit/await)."""
        cache = object.__getattribute__(self, "_cache")
        key   = object.__getattribute__(self, "_key")
        cache[key] = int(v)

    # ------------------------------------------------------------------
    # Délégation vers le signal parent pour tout attribut inconnu
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        if name in FieldProxy._RESERVED:
            return object.__getattribute__(self, name)
        signal = object.__getattribute__(self, "_signal")
        return getattr(signal, name)

    def __setattr__(self, name: str, val: Any) -> None:

        if name == "value":
            cache = object.__getattribute__(self, "_cache")
            key   = object.__getattribute__(self, "_key")
            cache[key] = int(val)
            return

        if name in FieldProxy._RESERVED:
            object.__setattr__(self, name, val)
            return
        field_name = object.__getattribute__(self, "_name")
        raise AttributeError(
            f"Utilise .value pour écrire : w.<port>.{field_name}.value = {val!r}"
        )

    # ------------------------------------------------------------------
    # Conversions Python
    # ------------------------------------------------------------------

    def __int__(self) -> int:
        return self.value

    def __index__(self) -> int:
        return self.value

    def __eq__(self, other: Any) -> bool:
        try:
            return self.value == int(other)
        except (TypeError, ValueError):
            return NotImplemented

    def __ne__(self, other: Any) -> bool:
        result = self.__eq__(other)
        return not result if result is not NotImplemented else result

    def __repr__(self) -> str:
        key  = object.__getattribute__(self, "_key")
        size = object.__getattribute__(self, "_size")
        try:
            val = self.value
        except Exception:
            val = "?"
        return f"FieldProxy({key!r}, size={size}, value={val})"


# ---------------------------------------------------------------------------
# StructProxy — port struct ou sous-struct imbriquée
# ---------------------------------------------------------------------------

class StructProxy:
    """
    Représente un port (ou sous-struct) de type struct.

    - ``proxy.mem_addr``           → ``FieldProxy``
    - ``proxy.sub_struct``         → ``StructProxy`` enfant
    - ``proxy.mem_addr.value``     → lecture du champ
    - ``proxy.mem_addr.value = v`` → écriture en cache
    - ``proxy.value``              → vecteur brut (LogicArray cocotb natif)
    - ``proxy.value = v``          → écriture directe bypass cache
    - Attribut inconnu             → délégué au signal cocotb sous-jacent

    Paramètres
    ----------
    struct_def : StructDef du parser
    signal     : handle cocotb du port racine (ex: dut.data_i)
    cache      : dict partagé (None = crée le sien)
    path       : chemin depuis la racine (ex: "data_i" ou "data_i.sub")
    """

    _RESERVED = frozenset({
        "_struct_def", "_signal", "_cache", "_path", "_offsets", "_children", "value",
    })

    def __init__(
        self,
        struct_def: StructDef,
        signal: Any,
        dut: HierarchyObject,
        cache: Optional[Dict[str, int]] = None,
        path: str = "",
    ) -> None:
        object.__setattr__(self, "_struct_def", struct_def)
        object.__setattr__(self, "_signal",     signal)
        object.__setattr__(self, "_path",       path)
        object.__setattr__(self, "_dut",        dut)

        shared_cache = cache if cache is not None else {}
        object.__setattr__(self, "_cache", shared_cache)

        offsets = _compute_offsets(struct_def)
        object.__setattr__(self, "_offsets", offsets)

        # Pré-instanciation récursive des StructProxy enfants
        children: Dict[str, "StructProxy"] = {}
        for member in struct_def.members:
            if isinstance(member, StructMember) and member.struct_def is not None:
                child_path = f"{path}.{member.name}" if path else member.name
                children[member.name] = StructProxy(
                    struct_def=member.struct_def,
                    signal=signal,
                    dut=dut,
                    cache=shared_cache,
                    path=child_path,
                )
        object.__setattr__(self, "_children", children)

    # ------------------------------------------------------------------
    # .value — vecteur brut
    # ------------------------------------------------------------------

    @property
    def value(self) -> Any:
        """Vecteur brut du signal (LogicArray cocotb natif)."""
        signal = object.__getattribute__(self, "_signal")
        return signal.value

    @value.setter
    def value(self, v: Any) -> None:
        """Écriture directe sur le vecteur (bypass cache)."""
        signal = object.__getattribute__(self, "_signal")
        signal.value = v

    # ------------------------------------------------------------------
    # Accès aux champs et sous-structs
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        if name in StructProxy._RESERVED:

            if name == "value":
                dut = object.__getattribute__(self, "_dut")
                name = object.__getattribute__(self, "_signal")
                signal = object.__getattribute__(dut, name)
                return signal.value

            return object.__getattribute__(self, name)

        children: Dict[str, StructProxy] = object.__getattribute__(self, "_children")

        if name in children:
            return children[name]

        struct_def: StructDef = object.__getattribute__(self, "_struct_def")
        member = next((m for m in struct_def.members if m.name == name), None)


        # Attribut inconnu → délègue au signal cocotb (ex: .driven, ._log)
        if member is None:
            signal = object.__getattribute__(self, "_signal")
            return getattr(signal, name)

        # Champ connu → FieldProxy
        signal  = object.__getattribute__(self, "_signal")
        cache   = object.__getattribute__(self, "_cache")
        offsets = object.__getattribute__(self, "_offsets")
        path    = object.__getattribute__(self, "_path")

        cache_key = f"{path}.{name}" if path else name
        offset    = offsets.get(name, 0)

        return FieldProxy(
            name=name,
            parent_signal=signal,
            cache=cache,
            cache_key=cache_key,
            offset=offset,
            size=member.size,
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in StructProxy._RESERVED:
            object.__setattr__(self, name, value)
            return
        raise AttributeError(
            f"Utilise .value pour écrire sur un champ : "
            f"w.<port>.{name}.value = {value!r}"
        )

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """
        Applique toutes les écritures en cache sur le signal cocotb.
        Stratégie read-modify-write : lit le vecteur courant, applique
        les bits modifiés, écrit le résultat, vide le cache.
        """
        cache      = object.__getattribute__(self, "_cache")
        signal     = object.__getattribute__(self, "_signal")
        path       = object.__getattribute__(self, "_path")
        struct_def = object.__getattribute__(self, "_struct_def")
        offsets    = object.__getattribute__(self, "_offsets")

        if not cache:
            return

        try:
            vector = int(signal.value)
        except Exception:
            vector = 0

        prefix = f"{path}." if path else ""

        for key, val in list(cache.items()):
            if path and not (key.startswith(prefix) or key == path):
                continue
            rel    = key[len(prefix):]
            parts  = rel.split(".")
            offset, size = self._resolve_path(parts, struct_def, offsets)
            if offset is None or size is None:
                continue
            mask   = (1 << size) - 1
            vector = (vector & ~(mask << offset)) | ((int(val) & mask) << offset)

        signal.value = vector

        keys_to_del = [
            k for k in cache
            if not path or k.startswith(prefix) or k == path
        ]
        for k in keys_to_del:
            del cache[k]

    def _resolve_path(
        self,
        parts: List[str],
        struct_def: StructDef,
        offsets: Dict[str, int],
    ) -> tuple:
        """Résout ['sub', 'field'] → (offset_global, size). (None, None) si invalide."""
        if not parts:
            return None, None
        name   = parts[0]
        member = next((m for m in struct_def.members if m.name == name), None)
        if member is None:
            return None, None
        base_offset = offsets.get(name, 0)
        if len(parts) == 1:
            return base_offset, member.size
        if isinstance(member, StructMember) and member.struct_def is not None:
            sub_offsets          = _compute_offsets(member.struct_def)
            sub_offset, sub_size = self._resolve_path(
                parts[1:], member.struct_def, sub_offsets
            )
            if sub_offset is None:
                return None, None
            return base_offset + sub_offset, sub_size
        return None, None

    def __int__(self) -> int:
        signal = object.__getattribute__(self, "_signal")
        return int(signal.value)

    def __repr__(self) -> str:
        struct_def = object.__getattribute__(self, "_struct_def")
        path       = object.__getattribute__(self, "_path")
        cache      = object.__getattribute__(self, "_cache")
        pending    = {k: v for k, v in cache.items() if k.startswith(path)}
        return (
            f"StructProxy(path={path!r}, type={struct_def.name!r}, pending={pending})"
        )


# ---------------------------------------------------------------------------
# _AwaitableCommit
# ---------------------------------------------------------------------------

class _AwaitableCommit:
    """Awaitable qui flush le cache puis délègue au trigger cocotb."""

    def __init__(self, wrapper: "DutWrapper", trigger: Any) -> None:
        self._wrapper = wrapper
        self._trigger = trigger

    def __await__(self):
        self._wrapper.commit()
        yield from self._trigger.__await__()


# ---------------------------------------------------------------------------
# DutWrapper — hérite de HierarchyObject
# ---------------------------------------------------------------------------

class DutWrapper(HierarchyObject):
    """
    Wrapper autour d'un DUT cocotb qui hérite de HierarchyObject.

    Réutilise le handle GPI du DUT : tout le comportement cocotb natif
    est conservé à l'identique. Seuls les ports déclarés dans ``port_types``
    sont interceptés pour retourner un ``StructProxy``.

    Paramètres
    ----------
    dut         : handle cocotb du DUT
    structs     : liste de StructDef issue de ``parse_verible_json()``
    port_types  : dict { nom_port: nom_type_struct }
                  Ex: {"data_i": "cache_op_t"}

    Exemples
    --------
    ::

        w = DutWrapper(dut, structs=structs, port_types={"data_i": "cache_op_t"})

        # Natif cocotb — aucune différence avec dut
        w.clk_i.value
        w.rst_ni.value = 0
        await RisingEdge(w.clk_i)

        # Ports struct
        w.data_i.mem_addr.value    = 0xFF
        w.data_i.nb_transfer.value = 27
        val = w.data_i.mem_addr.value
        raw = w.data_i.value

        # Flush auto avant trigger
        await w(RisingEdge(w.clk_i))

        # Flush manuel
        w.commit()
    """

    def __init__(
        self,
        dut: Any,
        structs: List[StructDef],
        port_types: Dict[str, str],
    ) -> None:
        # Initialise HierarchyObject avec le handle GPI du DUT
        # → comportement cocotb 100% natif pour tous les signaux
        super().__init__(dut._handle, dut._path)

        setattr(self, "_dut", dut)

        # struct_index: Dict[str, StructDef] = {s.name: s for s in structs}
        struct_index: Dict[str, StructDef] = structs

        proxies: Dict[str, StructProxy] = {}
        for port_name, type_name in port_types.items():
            struct_def = struct_index.get(type_name)
            if struct_def is None:
                raise ValueError(
                    f"Type '{type_name}' introuvable. "
                    f"Types disponibles : {list(struct_index.keys())}"
                )
            # Accès au signal via le DUT original pour avoir le vrai handle cocotb
            signal = getattr(dut, port_name, None)
            if signal is None:
                raise AttributeError(f"Signal '{port_name}' absent du DUT.")
            proxies[port_name] = StructProxy(
                struct_def=struct_def,
                signal=signal,
                dut=dut,
                path=port_name,
            )

        # object.__setattr__ pour contourner le __setattr__ de HierarchyObject
        # qui bloque les attributs non-GPI
        object.__setattr__(self, "_proxies", proxies)

    #     clk = [attr for attr in dir(dut) if attr.startswith("clk")]

    #     for clk_attr in clk:
    #         start_soon(self._auto_commit_loop(getattr(dut, clk_attr)))


    # async def _auto_commit_loop(wrapper, clk):
    #     while True:
    #         await RisingEdge(clk)
    #         wrapper.commit()

    # ------------------------------------------------------------------
    # __getattr__ : intercepte les ports struct, délègue le reste
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        # Accès aux proxies en passant par object.__getattribute__
        # pour éviter une récursion infinie
        clk = [attr for attr in dir(self._dut) if attr.startswith("clk")]

        if name in clk:
            self.commit()

        try:
            proxies = object.__getattribute__(self, "_proxies")
            if name in proxies:
                return proxies[name]
        except AttributeError:
            pass

        # Tout le reste → comportement HierarchyObject natif
        return super().__getattr__(name)

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """Flush tous les StructProxy dont le cache est non vide."""
        proxies = object.__getattribute__(self, "_proxies")
        for proxy in proxies.values():
            proxy.flush()

    # ------------------------------------------------------------------
    # await w(trigger)
    # ------------------------------------------------------------------

    def __call__(self, trigger: Any) -> _AwaitableCommit:
        """
        Retourne un awaitable qui flush le cache puis attend le trigger.

        Exemples ::

            await w(RisingEdge(w.clk_i))
            await w(Timer(10, units="ns"))
        """
        return _AwaitableCommit(wrapper=self, trigger=trigger)
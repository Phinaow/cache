"""
verible_struct_parser.py
========================
Parse un fichier JSON généré par Verible et retourne :

    {
        "parameters": { "MEM_ADDR_W": 32, "MEM_CACHE_SIZE": 4, ... },
        "structs":    { "cache_op_t": StructDef(...), ... },
        "enums":      { "rf_wb_e": EnumDef(size=1, values={"REFILL":0,...}), ... },
        "modules":    {
            "refill_engine": {
                "data_i": PortDef(direction="input", type_name="cache_op_t", size=47, obj=StructDef),
                "clk_i":  PortDef(direction="input", type_name="logic",      size=1,  obj=None),
            }
        }
    }

Règles :
  - structs/enums : uniquement dans les packages (ignorés dans les modules)
  - paramètres    : évalués dans l\'ordre, dépendances inter-paramètres résolues
  - best-effort   : size = -1 si expression non résolvable
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


# ===========================================================================
# Dataclasses
# ===========================================================================

@dataclass
class LogicMember:
    name: str
    msb:  int
    lsb:  int

    @property
    def size(self) -> int:
        return self.msb - self.lsb + 1

    def __repr__(self):
        return f"LogicMember(name={self.name!r}, msb={self.msb}, lsb={self.lsb})"
        # return f"LogicMember(name={self.name!r}, size={self.size}, range=[{self.msb}:{self.lsb}])"


@dataclass
class EnumMember:
    name:      str
    type_name: str
    size:      int

    def __repr__(self):
        return f"EnumMember(name={self.name!r}, type_name={self.type_name!r}, size={self.size})"


@dataclass
class StructMember:
    name:       str
    type_name:  str
    struct_def: "StructDef | None" = field(default=None, repr=False)

    @property
    def size(self) -> int:
        return -1 if self.struct_def is None else self.struct_def.total_size

    def __repr__(self):
        s = str(self.size) if self.size >= 0 else "unresolved"
        return f"StructMember(name={self.name!r}, type_name={self.type_name!r}, struct_def={self.struct_def})"


MemberType = Union[LogicMember, EnumMember, StructMember]


@dataclass
class StructDef:
    name:    str
    members: list[MemberType] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(m.size for m in self.members if m.size >= 0)

    def __repr__(self):
        lines = [f"StructDef(name={self.name!r}, members=["]
        for m in self.members:
            lines.append(f"    {m!r},")
        lines.append("])")
        return "\n".join(lines)


@dataclass
class EnumDef:
    """
    name   : nom du typedef
    size   : taille en bits
    values : { "REFILL": 0, "WRITEBACK": 1, ... }
    """
    name:   str
    size:   int
    values: dict[str, int] = field(default_factory=dict)

    def __repr__(self):
        return f"EnumDef(name={self.name!r}, size={self.size}, values={self.values!r})"


@dataclass
class PortDef:
    """
    direction : "input" | "output" | "inout"
    type_name : "logic" | nom_struct | nom_enum
    size      : taille en bits (-1 si non résolvable)
    obj       : StructDef | EnumDef | None
    """
    direction: str
    type_name: str
    size:      int
    obj: Union[StructDef, EnumDef, None] = field(default=None, repr=False)


    def __repr__(self):
        return (f"PortDef(direction={self.direction!r}, "
                f"type_name={self.type_name!r}, size={self.size}"
                f"{"" if self.obj is None else f", obj=" + str(self.obj)}" ")")


# ===========================================================================
# Utilitaires AST
# ===========================================================================

Node = dict

def _tag(n):      return n.get("tag", "")   if n else ""
def _text(n):     return n.get("text", "")  if n else ""
def _ch(n):       return [c for c in n.get("children", []) if c] if n else []

def _find_first(node, *tags):
    q = [node]
    while q:
        cur = q.pop(0)
        if not cur: continue
        if _tag(cur) in tags: return cur
        q.extend(_ch(cur))
    return None

def _find_all(node, *tags):
    res, stack = [], [node]
    while stack:
        cur = stack.pop()
        if not cur: continue
        if _tag(cur) in tags: res.append(cur)
        stack.extend(reversed(_ch(cur)))
    return res

def _dchild(node, tag_name):
    for c in _ch(node):
        if _tag(c) == tag_name: return c
    return None


# ===========================================================================
# Évaluateur d\'expressions
# ===========================================================================

def _literal(node) -> int | None:
    """Lit un entier depuis n\'importe quel nœud littéral."""
    # Cas spécial : kNumber avec kBaseDigits (ex: 1\'b0, 2\'d3)
    # La vraie valeur numérique est dans TK_BinDigits / TK_DecDigits / TK_HexDigits
    if _tag(node) == "kNumber":
        base_digits = _find_first(node, "kBaseDigits")
        if base_digits:
            bin_d = _find_first(base_digits, "TK_BinDigits")
            hex_d = _find_first(base_digits, "TK_HexDigits")
            dec_d = _find_first(base_digits, "TK_DecDigits")
            oct_d = _find_first(base_digits, "TK_OctDigits")
            if bin_d and _text(bin_d):
                try: return int(_text(bin_d).replace("_",""), 2)
                except ValueError: pass
            if hex_d and _text(hex_d):
                try: return int(_text(hex_d).replace("_",""), 16)
                except ValueError: pass
            if dec_d and _text(dec_d):
                try: return int(_text(dec_d).replace("_",""))
                except ValueError: pass
            if oct_d and _text(oct_d):
                try: return int(_text(oct_d).replace("_",""), 8)
                except ValueError: pass
        # Sinon lire TK_DecNumber directement
        dec = _find_first(node, "TK_DecNumber")
        if dec and _text(dec):
            try: return int(_text(dec).replace("_",""))
            except ValueError: pass
        return None

    num = _find_first(node, "TK_DecNumber","TK_HexNumber","TK_BinNumber","TK_OctNumber")
    if num and _text(num):
        raw = _text(num).replace("_","")
        try:
            t = _tag(num)
            if t == "TK_HexNumber": return int(raw.lstrip("0x").lstrip("0X") or "0", 16)
            if t == "TK_BinNumber": return int(raw.lstrip("0b").lstrip("0B") or "0", 2)
            if t == "TK_OctNumber": return int(raw.lstrip("0o").lstrip("0O") or "0", 8)
            return int(raw)
        except ValueError: return None
    return None


def _eval(node, params: dict[str, int]) -> int | None:
    """
    Évalue récursivement une expression Verible.
    Supporte : littéraux, refs paramètres, +/-/*//**/%/<</>>, $clog2, parenthèses.
    Retourne None si non résolvable.
    """
    if not node: return None
    t = _tag(node)

    # Littéraux directs
    if t in ("TK_DecNumber","TK_HexNumber","TK_BinNumber","TK_OctNumber"):
        return _literal(node)

    if t == "kNumber":
        return _literal(node)

    # Référence à un paramètre via kLocalRoot (nouveau format Verible)
    if t == "kLocalRoot":
        unq = _dchild(node, "kUnqualifiedId")
        if unq is None: unq = node
        sym = _find_first(unq, "SymbolIdentifier")
        if sym and _text(sym) in params:
            return params[_text(sym)]
        return None

    # kReference → kLocalRoot
    if t == "kReference":
        lr = _dchild(node, "kLocalRoot")
        return _eval(lr, params) if lr else None

    # kFunctionCall wrappant une référence simple
    if t == "kFunctionCall":
        ref = _dchild(node, "kReference")
        if ref: return _eval(ref, params)
        lr  = _find_first(node, "kLocalRoot")
        return _eval(lr, params) if lr else None

    # $clog2(expr)
    if t == "kSystemTFCall":
        fn = _find_first(node, "SystemTFIdentifier")
        if fn and _text(fn) == "$clog2":
            arg_list = _find_first(node, "kArgumentList")
            arg = _find_first(arg_list or node, "kExpression")
            val = _eval(arg, params) if arg else None
            if val is not None and val > 0:
                return max(1, math.ceil(math.log2(val)))
        return None

    # Opération binaire
    if t == "kBinaryExpression":
        ch = _ch(node)
        if len(ch) == 3:
            left  = _eval(ch[0], params)
            op    = _tag(ch[1])
            right = _eval(ch[2], params)
            if left is None or right is None: return None
            ops = {
                "+":  lambda a,b: a + b,
                "-":  lambda a,b: a - b,
                "*":  lambda a,b: a * b,
                "/":  lambda a,b: a // b,
                "**": lambda a,b: a ** b,
                "%":  lambda a,b: a  % b,
                "<<": lambda a,b: a << b,
                ">>": lambda a,b: a >> b,
            }
            return ops[op](left, right) if op in ops else None
        return None

    # Parenthèses
    if t == "kParenGroup":
        inner = _find_first(node, "kExpression")
        return _eval(inner, params) if inner else None

    # kExpression : enveloppe → descend dans le premier enfant
    if t == "kExpression":
        ch = _ch(node)
        return _eval(ch[0], params) if ch else None

    return None


def _dim_range(node, params) -> tuple[int,int] | None:
    """Retourne (MSB, LSB) depuis le premier kDimensionRange sous node."""
    dr = _find_first(node, "kDimensionRange")
    if not dr: return None
    exprs = _find_all(dr, "kExpression")
    if len(exprs) < 2: return None
    msb = _eval(exprs[0], params)
    lsb = _eval(exprs[1], params)
    if msb is None or lsb is None: return None
    return (msb, lsb)


# ===========================================================================
# Collecte des paramètres
# ===========================================================================

def collect_parameters(root: Node) -> dict[str, int]:
    """
    Collecte tous les paramètres du package en résolvant les dépendances
    dans l\'ordre de déclaration.

    Supporte :
      512 * 2**20
      (CPU_CACHE_SIZE * CPU_ADDR_W) / MEM_DATA_W
      $clog2(MEM_CACHE_SIZE)
      CACHE_SIZE / NB_LINE
    """
    params: dict[str, int] = {}
    for pd in _find_all(root, "kParamDeclaration"):
        pt = _dchild(pd, "kParamType")
        if not pt: continue
        name_node = _find_first(pt, "SymbolIdentifier")
        if not name_node: continue
        name = _text(name_node)
        trailing = _dchild(pd, "kTrailingAssign")
        if not trailing: continue
        expr = _find_first(trailing, "kExpression")
        if not expr: continue
        val = _eval(expr, params)
        if val is not None:
            params[name] = val
    return params


# ===========================================================================
# Collecte des enums
# ===========================================================================

def _enum_values(enum_type_node, params) -> dict[str, int]:
    """Extrait les constantes nommées avec auto-incrément et valeurs explicites."""
    values, auto = {}, 0
    brace = _find_first(enum_type_node, "kBraceGroup")
    if not brace: return values
    for en in _find_all(brace, "kEnumName"):
        sym = _find_first(en, "SymbolIdentifier")
        if not sym: continue
        name = _text(sym)
        trailing = _dchild(en, "kTrailingAssign")
        if trailing:
            expr = _find_first(trailing, "kExpression")
            v    = _eval(expr, params) if expr else None
            if v is not None:
                auto = v
        values[name] = auto
        auto += 1
    return values


def collect_enums(root: Node, params: dict[str, int]) -> dict[str, EnumDef]:
    """Collecte les typedef enum d\'un package."""
    enums: dict[str, EnumDef] = {}
    for td in _find_all(root, "kTypeDeclaration"):
        syms = [c for c in _ch(td) if _tag(c) == "SymbolIdentifier"]
        if not syms: continue
        typedef_name = _text(syms[-1])
        dt = _find_first(td, "kDataType")
        if not dt: continue
        et = _find_first(dt, "kEnumType")
        if not et: continue

        # Taille : type de base ou inférence par comptage
        size = None
        base_dt = _dchild(et, "kDataType")
        if base_dt:
            dim = _dim_range(base_dt, params)
            if dim: size = dim[0] - dim[1] + 1
        if size is None:
            nb   = len(_find_all(et, "kEnumName"))
            size = max(1, math.ceil(math.log2(nb))) if nb > 1 else 1

        enums[typedef_name] = EnumDef(
            name   = typedef_name,
            size   = size,
            values = _enum_values(et, params),
        )
    return enums


# ===========================================================================
# Collecte des structs
# ===========================================================================

def _resolve_member(member_node, params, enum_defs) -> MemberType | None:
    id_dims = _find_first(member_node, "kDataTypeImplicitIdDimensions")
    if not id_dims: return None

    member_name = ""
    for c in _ch(id_dims):
        if _tag(c) == "SymbolIdentifier":
            member_name = _text(c)
            break
    if not member_name: return None

    dt = _dchild(id_dims, "kDataType")
    if not dt: return None

    primitive  = _find_first(dt, "kDataTypePrimitive")
    local_root = _dchild(dt, "kLocalRoot")

    # logic
    if primitive and _find_first(primitive, "logic"):
        dim = _dim_range(dt, params)
        msb, lsb = dim if dim else (0, 0)
        return LogicMember(name=member_name, msb=msb, lsb=lsb)

    # type nommé : enum ou struct
    if local_root:
        unq = _dchild(local_root, "kUnqualifiedId")
        sym = _find_first(unq or local_root, "SymbolIdentifier")
        if sym:
            type_name = _text(sym)
            if type_name in enum_defs:
                return EnumMember(name=member_name, type_name=type_name,
                                  size=enum_defs[type_name].size)
            return StructMember(name=member_name, type_name=type_name)

    return None


def collect_structs(root, params, enum_defs) -> dict[str, StructDef]:
    """Collecte les typedef struct d\'un package."""
    structs: dict[str, StructDef] = {}
    for td in _find_all(root, "kTypeDeclaration"):
        st = _find_first(td, "kStructType")
        if not st: continue
        syms = [c for c in _ch(td) if _tag(c) == "SymbolIdentifier"]
        if not syms: continue
        name = _text(syms[-1])
        sdef = StructDef(name=name)
        for mn in _find_all(st, "kStructUnionMember"):
            m = _resolve_member(mn, params, enum_defs)
            if m: sdef.members.append(m)
        structs[name] = sdef
    return structs


def resolve_struct_refs(structs: dict[str, StructDef]) -> None:
    """Résout StructMember.struct_def pour chaque membre struct."""
    for s in structs.values():
        for m in s.members:
            if isinstance(m, StructMember) and m.struct_def is None:
                m.struct_def = structs.get(m.type_name)


# ===========================================================================
# Collecte des ports de module
# ===========================================================================

def collect_modules(root, params, structs, enums) -> dict[str, dict[str, PortDef]]:
    """Collecte les modules et leurs ports d\'entrée/sortie."""
    modules: dict[str, dict[str, PortDef]] = {}

    for mod_decl in _find_all(root, "kModuleDeclaration"):
        header = _dchild(mod_decl, "kModuleHeader")
        if not header: continue
        mod_sym = _find_first(header, "SymbolIdentifier")
        if not mod_sym: continue
        mod_name = _text(mod_sym)

        ports: dict[str, PortDef] = {}

        for pd in _find_all(mod_decl, "kPortDeclaration"):
            # Direction
            direction = "unknown"
            for c in _ch(pd):
                if _tag(c) in ("input","output","inout"):
                    direction = _tag(c)
                    break

            # Nom du port
            uid = _dchild(pd, "kUnqualifiedId")
            sym = _find_first(uid, "SymbolIdentifier") if uid else None
            if not sym: continue
            port_name = _text(sym)

            dt = _dchild(pd, "kDataType")
            if not dt: continue

            primitive  = _find_first(dt, "kDataTypePrimitive")
            local_root = _dchild(dt, "kLocalRoot")

            # logic
            if primitive and _find_first(primitive, "logic"):
                dim  = _dim_range(dt, params)
                size = (dim[0] - dim[1] + 1) if dim else 1
                ports[port_name] = PortDef(
                    direction=direction, type_name="logic", size=size, obj=None)

            # type nommé
            elif local_root:
                unq  = _dchild(local_root, "kUnqualifiedId")
                tsym = _find_first(unq or local_root, "SymbolIdentifier")
                if not tsym: continue
                type_name = _text(tsym)
                if type_name in structs:
                    obj  = structs[type_name]
                    size = obj.total_size
                elif type_name in enums:
                    obj  = enums[type_name]
                    size = obj.size
                else:
                    obj, size = None, -1
                ports[port_name] = PortDef(
                    direction=direction, type_name=type_name, size=size, obj=obj)

        modules[mod_name] = ports

    return modules


# ===========================================================================
# Point d\'entrée public
# ===========================================================================

def parse_verible_json(
    json_path: str | Path,
    param_overrides: dict[str, int] | None = None,
) -> dict:
    """
    Parse un fichier JSON Verible et retourne :

        {
            "parameters": dict[str, int],
            "structs":    dict[str, StructDef],
            "enums":      dict[str, EnumDef],
            "modules":    dict[str, dict[str, PortDef]],
        }

    param_overrides : surcharge des valeurs de paramètres
                      Ex: {"MEM_ADDR_W": 64}
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    all_params:  dict[str, int]                = {}
    all_structs: dict[str, StructDef]          = {}
    all_enums:   dict[str, EnumDef]            = {}
    all_modules: dict[str, dict[str, PortDef]] = {}

    # Passe 1 : packages → paramètres, enums, structs
    for _filename, file_data in data.items():
        root = file_data.get("tree")
        if not root: continue
        if not _find_first(root, "kPackageDeclaration"): continue

        params = collect_parameters(root)
        if param_overrides:
            params.update(param_overrides)
        all_params.update(params)

        enums = collect_enums(root, params)
        all_enums.update(enums)

        structs = collect_structs(root, params, {**all_enums})
        all_structs.update(structs)

    resolve_struct_refs(all_structs)

    # Passe 2 : modules → ports
    for _filename, file_data in data.items():
        root = file_data.get("tree")
        if not root: continue
        if not _find_first(root, "kModuleDeclaration"): continue
        modules = collect_modules(root, all_params, all_structs, all_enums)
        all_modules.update(modules)

    return {
        "parameters": all_params,
        "structs":    all_structs,
        "enums":      all_enums,
        "modules":    all_modules,
    }


def pretty_print(result: dict) -> None:
    print("=" * 60)
    print("PARAMÈTRES")
    print("=" * 60)
    for name, val in result["parameters"].items():
        print(f"  {name:<28} = {val}")

    print()
    print("=" * 60)
    print("ENUMS")
    print("=" * 60)
    for name, e in result["enums"].items():
        print(f"  {name}  ({e.size} bits)")
        for const, val in e.values.items():
            print(f"    {const} = {val}")

    print()
    print("=" * 60)
    print("STRUCTS")
    print("=" * 60)
    for name, s in result["structs"].items():
        print(f"  {name}  ({s.total_size} bits)")
        for m in s.members:
            if isinstance(m, LogicMember):
                print(f"    [logic]  {m.name:<24} size={m.size}  [{m.msb}:{m.lsb}]")
            elif isinstance(m, EnumMember):
                print(f"    [enum]   {m.name:<24} type={m.type_name}  size={m.size}")
            elif isinstance(m, StructMember):
                print(f"    [struct] {m.name:<24} type={m.type_name}  size={m.size}")

    print()
    print("=" * 60)
    print("MODULES")
    print("=" * 60)
    for mod_name, ports in result["modules"].items():
        print(f"  module {mod_name}")
        for port_name, p in ports.items():
            print(f"    [{p.direction:<6}] {port_name:<26} type={p.type_name:<16} size={p.size}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <verible_output.json>")
        sys.exit(1)
    result = parse_verible_json(sys.argv[1])
    # pretty_print(result)

    with open("generated_config.py", "w", encoding="utf-8") as f:
        f.write(f"from verible_struct_parser import *\n\nresult={repr(result)}\n")
        for name, parameters in result["parameters"].items():
            f.write(f"{name} = {parameters}\n")

        for k, v in result["enums"].items():
            for name, value in v.values.items():
                f.write(f"{name} = {value}\n")

        f.close()

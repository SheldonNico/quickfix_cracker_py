from __future__ import annotations
import typing as t
import xml, os, re, attr
import xml.etree.ElementTree
from collections import OrderedDict

# ref to: quickfix/include/quickfix/FieldTypes.h, the only type need to be carefully processed is UTCTIMESTAMP
#
# typedef UtcDate UtcDateOnly;
# typedef std::string STRING;
# typedef char CHAR;
# typedef double PRICE;
# typedef int INT;
# typedef double AMT;
# typedef double QTY;
# typedef std::string CURRENCY;
# typedef std::string MULTIPLEVALUESTRING;
# typedef std::string MULTIPLESTRINGVALUE;
# typedef std::string MULTIPLECHARVALUE;
# typedef std::string EXCHANGE;
# typedef UtcTimeStamp UTCTIMESTAMP;
# typedef bool BOOLEAN;
# typedef std::string LOCALMKTDATE;
# typedef std::string DATA;
# typedef double FLOAT;
# typedef double PRICEOFFSET;
# typedef std::string MONTHYEAR;
# typedef std::string DAYOFMONTH;
# typedef UtcDate UTCDATE;
# typedef UtcDateOnly UTCDATEONLY;
# typedef UtcTimeOnly UTCTIMEONLY;
# typedef int NUMINGROUP;
# typedef double PERCENTAGE;
# typedef int SEQNUM;
# typedef int LENGTH;
# typedef std::string COUNTRY;
# typedef std::string TZTIMEONLY;
# typedef std::string TZTIMESTAMP;
# typedef std::string XMLDATA;
# typedef std::string LANGUAGE;
TYP_MAP: dict[str, t.Any] = {
    'STRING': str,
    'CURRENCY': str,
    'MULTIPLEVALUESTRING': str,
    'MULTIPLESTRINGVALUE': str,
    'MULTIPLECHARVALUE': str,
    'EXCHANGE': str,
    'LOCALMKTDATE': str,
    'DATA': str,
    'MONTHYEAR': str,
    'DAYOFMONTH': str,
    'COUNTRY': str,
    'TZTIMEONLY': str,
    'TZTIMESTAMP': str,
    'XMLDATA': str,
    'LANGUAGE': str,

    # NOTE: UTCTIMESTAMP is the only type that use `USER_DEFINE_UTCTIMESTAMP` defined
    # and it can't not be construct through python type
    #
    # ref: https://github.com/quickfix/quickfix/issues/251
    'UTCTIMESTAMP': str,

    'UTCDATE': str,
    'UTCDATEONLY': str,
    'UTCTIMEONLY': str,
    'DATE': str,
    'TIME': str,

    'CHAR': str, # char or string?

    'BOOLEAN': bool,

    'PRICEOFFSET': float,
    'FLOAT': float,
    'PRICE': float,
    'AMT': float,
    'QTY': float,
    'PERCENTAGE': float,

    'INT': int,
    'NUMINGROUP': int,
    'SEQNUM': int,
    'LENGTH': int,

    # added in 20210914
    'NumInGroup': int,
}

CAMEL_PATTERN = re.compile('((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))')
def camel_to_sname(name: str) -> str:
    return CAMEL_PATTERN.sub(r'_\1', name).lower()

def to_ns_name(ns: str, name: str) -> str:
    assert name.find(".") < 0, f"illegal name: `{name}`"
    if len(ns) > 0:
        return ns + "." + name
    else:
        return name

def from_ns_name(name: str) -> str:
    return name.split(".")[-1]

@attr.s
class FieldMeta:
    number: int = attr.ib()
    name: str = attr.ib()
    type_name: str = attr.ib()

    enums: list[t.Tuple[str, str]] = attr.ib()

@attr.s
class Item:
    name: str = attr.ib()
    required: str = attr.ib()
    kind: t.Literal['field', 'group', 'component'] = attr.ib()

    def is_field(self) -> bool:
        return self.kind == "field"

    def is_group(self) -> bool:
        return self.kind == "group"

    def is_component(self) -> bool:
        return self.kind == "component"

@attr.s
class ClassMeta:
    ns_name: str = attr.ib()
    msgcat: t.Optional[str] = attr.ib()
    msgtype: t.Optional[str] = attr.ib()

    items: OrderedDict[str, Item] = attr.ib()

    def __str__(self) -> str:
        msg = f"{self.ns_name}:"
        for item in self.items.values():
            msg += "\n"
            msg += f"\t{item.kind} {item.name} \'{item.required}\'"

        return msg

@attr.s
class ComponentMeta:
    ns_name: str = attr.ib()

    items: OrderedDict[str, Item] = attr.ib()

def traverse_fields_rec(element: xml.etree.ElementTree.Element, map_fields: dict[str, FieldMeta]) -> None:
    number = int(element.attrib["number"])
    name = element.attrib["name"]
    typ = element.attrib["type"]

    assert name.find(".") < 0
    assert typ in TYP_MAP, f"unknown typ: `{typ}`"
    field = FieldMeta(number, name, typ, [])
    assert field.name not in map_fields, f"duplicated field number: {field} vs {map_fields[field.name]}"
    for enum in element:
        if enum.tag == "value":
            value = enum.attrib["enum"]
            field.enums.append((value, enum.attrib["description"]))
        else:
            raise RuntimeError(f"not possible: field enums is nested, got tag `{enum.tag}`...")

    map_fields[field.name] = field

def traverse_fields(doc: xml.etree.ElementTree.ElementTree) -> dict[str, FieldMeta]:
    map_fields: dict[str, FieldMeta] = {}

    fields = doc.find("fields")
    assert fields is not None
    for field in fields:
        assert field.tag == "field"
        traverse_fields_rec(field, map_fields)

    types = set(f.type_name for f in map_fields.values())
    print(f"fields found: #{len(map_fields)}, type: {len(types)}, {types}")
    return map_fields

def traverse_components_rec(
    element: xml.etree.ElementTree.Element,
    map_components: dict[str, ComponentMeta],
    ns: str
) -> None:
    name = element.attrib["name"]
    ns_name = to_ns_name(ns, name)
    component = ComponentMeta(ns_name, OrderedDict())
    assert ns_name not in map_components, f"duplicated component: {component} vs {map_components[ns_name]}"
    map_components[ns_name] = component

    for item in element:
        if item.tag == "field":
            item_name = item.attrib["name"]
            item_required = item.attrib["required"]
            assert item_name not in component.items
            component.items[item_name] = Item(item_name, item_required, "field")
        elif item.tag == "group":
            item_name = item.attrib["name"]
            item_required = item.attrib["required"]
            assert item_name not in component.items
            component.items[item_name] = Item(item_name, item_required, "group")
            traverse_components_rec(item, map_components, ns_name)
        elif item.tag == "component":
            item_name = item.attrib["name"]
            item_required = item.attrib["required"]
            assert item_name not in component.items, "component live in the global namespace, if not we should change code here"
            component.items[item_name] = Item(item_name, item_required, "component")
        else:
            raise RuntimeError(f"not possible for component, got tag: {item.tag}@{item.attrib}")

def traverse_components(doc: xml.etree.ElementTree.ElementTree) -> dict[str, ComponentMeta]:
    map_components: dict[str, ComponentMeta] = {}

    components = doc.find("components")
    if components is not None:
        for component in components:
            assert component.tag == "component"
            traverse_components_rec(component, map_components, "")

    print(f"components found: #{len(map_components)}")
    return map_components

def expand_component_rec(
    class_meta: ClassMeta, group_or_component: t.Union[ComponentMeta, ClassMeta], map_classes: dict[str, ClassMeta],
    map_components: dict[str, ComponentMeta], ns_name: str,
) -> None:
    for item in group_or_component.items.values():
        if item.is_field():
            assert item.name not in class_meta.items
            class_meta.items[item.name] = item
        elif item.is_group():
            assert item.name not in class_meta.items
            class_meta.items[item.name] = item
            # if ns_name.find(".") > 0:
            #     print(ns_name, item.name)

            #     raise

            ns_name = to_ns_name(class_meta.ns_name, item.name)
            sub_class_meta = ClassMeta(ns_name, None, None, OrderedDict())
            assert ns_name not in map_classes, "duplicated class in expanding..."
            map_classes[ns_name] = sub_class_meta
            ns_component_name = to_ns_name(group_or_component.ns_name, item.name)
            assert ns_component_name in map_components, f"component live in global namespace and differ from class: {ns_component_name}"
            sub_group = map_components[ns_component_name]
            expand_component_rec(sub_class_meta, sub_group, map_classes, map_components, ns_name)
        elif item.is_component():
            assert item.name in map_components
            sub_component = map_components[item.name]
            expand_component_rec(class_meta, sub_component, map_classes, map_components, class_meta.ns_name)
            # the difference between between group and component is how it handle namespace
        else:
            raise RuntimeError("not possible")

def traverse_classes_rec(
    ns: str,
    element: xml.etree.ElementTree.Element,
    map_classes: dict[str, ClassMeta],
    map_components: dict[str, ComponentMeta]
) -> None:
    name = element.attrib["name"]
    ns_name = to_ns_name(ns, name)
    if len(ns) == 0:
        msgcat: t.Optional[str] = element.attrib["msgcat"]
        msgtype: t.Optional[str] = element.attrib["msgtype"]
    else:
        msgcat = None
        msgtype = None
    assert ns_name not in map_classes, f"class duplicated: {ns_name} vs {map_classes[ns_name]}"
    class_meta = ClassMeta(ns_name, msgcat, msgtype, OrderedDict())
    map_classes[ns_name] = class_meta

    for item in element:
        if item.tag == "field":
            item_name = item.attrib["name"]
            item_required = item.attrib["required"]
            assert item_name not in class_meta.items
            class_meta.items[item_name] = Item(item_name, item_required, "field")
        elif item.tag == "group":
            item_name = item.attrib["name"]
            item_required = item.attrib["required"]
            assert item_name not in class_meta.items
            class_meta.items[item_name] = Item(item_name, item_required, "group")
            traverse_classes_rec(ns_name, item, map_classes, map_components)
        elif item.tag == "component":
            item_name = item.attrib["name"]
            item_required = item.attrib["required"]
            assert item_name not in class_meta.items
            component = map_components[item_name]
            expand_component_rec(class_meta, component, map_classes, map_components, ns_name)
        else:
            raise RuntimeError(f"not possible, got tag: {item.tag}@{item.attrib}")

def traverse_classes(doc: xml.etree.ElementTree.ElementTree, map_components: dict[str, ComponentMeta]) -> dict[str, ClassMeta]:
    map_classes: dict[str, ClassMeta] = {}

    messages = doc.find("messages")
    assert messages is not None

    for message in messages:
        assert message.tag == "message"
        traverse_classes_rec("", message, map_classes, map_components)

    return map_classes

def get_ids(class_meta: ClassMeta, map_fields: dict[str, FieldMeta]) -> t.Tuple[int, list[int]]:
    item_name = class_meta.ns_name.split(".")[-1]
    id_g = map_fields[item_name].number
    ids_g = []
    for item in class_meta.items.values():
        ids_g.append(map_fields[item.name].number)
    assert len(ids_g) > 0, "group has zero field"
    ids_g.append(0)
    return (id_g, ids_g)

def generate_class_def(
    depth: int, s_tab: str, class_meta: ClassMeta, map_classes: dict[str, ClassMeta], map_fields: dict[str, FieldMeta]
) -> str:
    s_depth = s_tab*depth
    s_name = class_meta.ns_name.split(".")[-1]
    s_ns_name = class_meta.ns_name
    s_at = f"{s_depth}@dataclass"
    s_class = f"{s_depth}class {s_name}:"
    s_at_classmethod = f"{s_depth}{s_tab}@classmethod"
    s_def_from_raw = f"{s_depth}{s_tab}def from_raw(cls, m: fix.Message) -> {s_ns_name}:"
    s_def_to_raw_rtn = "fix.Message" if s_ns_name.find(".") < 0 else "fix.Group"
    s_def_to_raw = f"{s_depth}{s_tab}def to_raw(self) -> {s_def_to_raw_rtn}:"

    s_fields, s_def_getter, s_def_rtn, s_def_to_raw_body, s_sub_class = [], [], [], [], []
    if s_ns_name.find(".") < 0:
        s_def_to_raw_body.append("m = fix.Message()")
        s_def_to_raw_body.append(f"m.getHeader().setField(fix.StringField(35, \"{class_meta.msgtype}\"))")
    else:
        id_g, ids_g = get_ids(class_meta, map_fields)
        s_def_to_raw_body.append(f"m = fix.Group({id_g}, {ids_g[0]}, int_arr({ids_g!r}))")

    for idx_ori, (item_name, item) in enumerate(class_meta.items.items()):
        s_item_name = valid_ident(camel_to_sname(item_name))
        assert s_item_name != item_name, "name conflicts, we assume all fields names follow CamelCase and is a CamelCase"
        assert item.required in ["", "Y", "N"]
        is_default = 1
        if item.is_field():
            field = map_fields[item_name]
            typeto = TYP_MAP[field.type_name]
            s_item_type = {str: "str", int: "int", float: "float", bool: "bool"}[typeto]

            if len(field.enums) > 0:
                assert field.type_name != "UTCTIMESTAMP", "wtf, a timestamp as enum?"
                s_enum_convert = s_item_type
                s_item_type = f"_enums.{field.name}"
                if typeto == bool:
                    s_getter = f"{s_item_type}(_bool(m.getField({field.number})))"
                else:
                    s_getter = f"{s_item_type}({s_enum_convert}(m.getField({field.number})))"
                s_setter_convert_back = f"self.{s_item_name}.value"
            else:
                if typeto == bool:
                    s_getter = f"_bool(m.getField({field.number}))"
                else:
                    s_getter = f"{s_item_type}(m.getField({field.number}))"
                s_setter_convert_back = f"self.{s_item_name}"

            # Dirty patch
            if field.type_name == "UTCTIMESTAMP":
                s_setter = f"m.setField(set_utctimestamp({field.number}, self.{s_item_name}))"
            else:
                s_convert_back = {bool: "BoolField", int: "IntField", float: "DoubleField", str: "StringField"}[typeto]
                s_setter = f"m.setField(fix.{s_convert_back}({field.number}, {s_setter_convert_back}))"

            if item.required != "Y":
                s_item_type = f"t.Optional[{s_item_type}]"
                s_default = " = None"
                s_getter = f"{s_getter} if m.isSetField({field.number}) else None"
                s_setter = f"if self.{s_item_name} is not None: {s_setter}"
            else:
                is_default = 0
                s_default = ""
        elif item.is_group():
            sub_class_meta = map_classes[f"{s_ns_name}.{item_name}"]
            id_g, ids_g = get_ids(sub_class_meta, map_fields)
            s_item_type = f"list[{s_ns_name}.{item_name}]"
            s_default = " = field(default_factory=list)"
            s_getter = f"get_group_by(m, {id_g}, {ids_g!r}, {s_ns_name}.{item_name}.from_raw) # noqa"
            s_setter = f"for g in self.{s_item_name}: m.addGroup(g.to_raw())"
            s_sub_class.append(generate_class_def(depth+1, s_tab, sub_class_meta, map_classes, map_fields))
        else:
            raise RuntimeError("component must be expanded before generate definitions")
        s_fields.append((is_default, idx_ori, f"{s_item_name}: {s_item_type}{s_default}"))
        s_def_getter.append(f"{s_item_name} = {s_getter}")
        s_def_rtn.append(f"{s_item_name}={s_item_name}")
        s_def_to_raw_body.append(s_setter)

    s_fields.sort()

    s_fields = "\n".join([f"{s_depth}{s_tab}{s}" for _, _, s in s_fields])
    s_def_getter = "\n".join([f"{s_depth}{s_tab}{s_tab}{s}" for s in s_def_getter])
    s_def_rtn = "{}{}{}return cls({})".format(s_depth, s_tab, s_tab, ", ".join(s_def_rtn))
    s_def_to_raw_body = "\n".join([f"{s_depth}{s_tab}{s_tab}{s}" for s in s_def_to_raw_body])
    s_def_to_raw_end = f"{s_depth}{s_tab}{s_tab}return m"

    s_sub_class = "\n".join(s_sub_class)
    s_sub_class_blank = "\n" if len(s_sub_class) > 0 else ""

    return f"""{s_at}
{s_class}
{s_fields}

{s_at_classmethod}
{s_def_from_raw}
{s_def_getter}
{s_def_rtn}

{s_def_to_raw}
{s_def_to_raw_body}
{s_def_to_raw_end}
{s_sub_class_blank}{s_sub_class}"""

def write_class_to_file(
    fpath: str, class_meta: ClassMeta, map_classes: dict[str, ClassMeta], map_fields: dict[str, FieldMeta]
) -> None:
    print(f"working in {fpath}")
    s_imports = """from __future__ import annotations
import typing as t # noqa
import quickfix as fix
from dataclasses import dataclass, field # noqa
from . import _bool, int_arr, get_group_by, set_utctimestamp # noqa
from . import _enums # noqa"""

    s_class = generate_class_def(0, " "*4, class_meta, map_classes, map_fields)

    with open(fpath, "w") as fh:
        fh.write(f"""{s_imports}

{s_class}
""")

def valid_ident(tag: str) -> str:
    if tag[0].isdigit() or tag in ["yield"]:
        return "_" + tag
    else:
        return tag

def write_enums_to_file(
    fname: str,
    field_map: dict[str, FieldMeta],
) -> list[str]:
    tabs = " " * 4
    enums = []
    out = []
    for fk, fm in field_map.items():
        if len(fm.enums) == 0: continue
        out.append(fk)
        typeto = TYP_MAP[fm.type_name]
        typefun = {
            str: str,
            int: int,
            float: float,
            bool: lambda x: {"Y": True, "N": False, "": False}[x]
        }[typeto]
        assert fm.type_name != "UTCTIMESTAMP", "WTF? you want a timesatmp as enum"
        field_s = []
        names = set()
        for nm, tag in fm.enums:
            nm_deduplicated = valid_ident(tag)
            count = 1
            while nm_deduplicated in names:
                assert count < 10, f"WTF: enums with same name: {nm_deduplicated}"
                nm_deduplicated = f"_{nm_deduplicated}"
                count += 1
            field_s.append(f"{nm_deduplicated} = {typefun(nm)!r}") # type: ignore
            names.add(nm_deduplicated)

        field_s = "\n".join([f"{tabs}{s}" for s in field_s])
        enums.append(f"""
class {fk}(enum.Enum):
{field_s}""")

    enums_s = "\n".join(enums)
    with open(fname, "w") as fh:
        fh.write(f"""import enum
{enums_s}
""")
    return out

def write_init_to_file(
    fname: str,
    map_classes: dict[str, ClassMeta],
    enums: list[str],
    BeginString: str,
    modules: dict[str, str],
) -> None:
    s_BeginString = f"BeginString: str = {BeginString!r}"
    s_tabs = " " * 4
    s_import_class = "\n".join([f"from .{m.lower()} import {m} # noqa" for m in modules.values()])
    s_MESSAGES = "\n".join([f"{s_tabs}{k!r}: ({m}, \"on_{m}\")," for k, m in modules.items()])
    s_import_enums = "from ._enums import * # noqa"
    s_all = [m for m in modules.values()] + enums
    s_all = f"__all__ = {s_all!r} # noqa"

    with open(fname, "w") as fh:
        fh.write(f"""from __future__ import annotations
import typing as t # noqa
import quickfix as fix

{s_BeginString}
{s_import_enums}

def _bool(x: str) -> bool:
    return {{"Y": True, "N": False}}[x]

def int_arr(arr: list[int]) -> fix.IntArray:
    ia = fix.IntArray(len(arr))
    for i, li in enumerate(arr): ia[i] = li
    return ia

def get_group_by(m: fix.Message, idx: int, ids: list[int], func: t.Any) -> list[t.Any]:
    out = []
    if m.isSetField(idx):
        g = fix.Group(idx, ids[0], ids, int_arr(ids))
        max_len = m.getField(id)
        for gi in range(1, 1+max_len):
            m.getGroup(gi, g)
            out.append(func(g))
    else:
        pass
    return out

def set_utctimestamp(id: int, s: str) -> fix.UtcTimeStamp:
    ts = fix.UtcTimeStampField(id)
    ts.setString(s)
    return ts

{s_import_class}
MESSAGES: dict[str, t.Tuple[t.Any, str]] = {{
{s_MESSAGES}
}}

def from_raw(message: fix.Message) -> t.Any:
    MsgType = fix.MsgType()
    message.getHeader().getField(MsgType)
    MsgType = MsgType.getString()
    if MsgType in MESSAGES:
        m, _ = MESSAGES[MsgType]
        return m.from_raw(message)
    else:
        return message

def crack(obj: t.Any, message: fix.Message, default: t.Any, *args: t.Any, **kwargs: t.Any) -> None:
    MsgType = fix.MsgType()
    message.getHeader().getField(MsgType)
    MsgType = MsgType.getString()
    if MsgType in MESSAGES:
        to, name = MESSAGES[MsgType]
        m = to.from_raw(message)
        if hasattr(obj, name):
            func = getattr(obj, name)
        else:
            func = default
    else:
        func = default
        m = message
    func(m, *args, **kwargs)

{s_all}""")

def write_to_files(
    map_classes: dict[str, ClassMeta],
    map_fields: dict[str, FieldMeta],
    dirname: str,
    BeginString: str,
) -> None:
    print(f"saving generated files to {dirname}")
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    else:
        pass
        # for item in os.listdir(dirname): shutil.rmtree(item)

    modules: dict[str, str] = {}
    for class_name, class_meta in map_classes.items():
        if class_meta.msgtype is None: continue
        assert class_meta.ns_name.find(".") < 0
        write_class_to_file(os.path.join(dirname, f"{class_name.lower()}.py"), class_meta, map_classes, map_fields)
        modules[class_meta.msgtype] = class_meta.ns_name

    enums = write_enums_to_file(os.path.join(dirname, "_enums.py"), map_fields)
    write_init_to_file(os.path.join(dirname, "__init__.py"), map_classes, enums, BeginString, modules)

def mainfun(spec_dir: str, target_dir: str, v_major: int, v_minor: int, v_sp: int) -> None:
    fname = f"FIX{v_major}{v_minor}.xml" if v_sp == 0 else f"FIX{v_major}{v_minor}SP{v_sp}.xml"
    fpath = os.path.join(spec_dir, fname)
    assert os.path.exists(fpath), f"spec xml not found: {fpath}"
    doc = xml.etree.ElementTree.parse(fpath)

    map_fields = traverse_fields(doc)
    map_components = traverse_components(doc)
    map_classes = traverse_classes(doc, map_components)

    BeginString = f"FIX.{v_major}.{v_minor}"

    mname = os.path.splitext(os.path.basename(fname))[0].lower()
    write_to_files(
        map_classes,
        map_fields,
        os.path.join(target_dir, mname),
        BeginString,
    )

if __name__ == "__main__":
    mainfun("./spec/", "./spec/", 4, 3, 0)


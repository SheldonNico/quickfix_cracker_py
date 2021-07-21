from __future__ import annotations
import typing as t
import xml, os, re, attr
import xml.etree.ElementTree

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
}

@attr.s
class FieldMeta:
    number: int = attr.ib()
    name: str = attr.ib()
    typ: str = attr.ib()

    enums: list[t.Tuple[str, str]] = attr.ib()

@attr.s
class ClassMeta:
    name: str = attr.ib()
    msgcat: str = attr.ib()
    msgtype: str = attr.ib()

    fields: dict[str, str] = attr.ib()
    subclass: set[str] = attr.ib()

@attr.s
class SubClassMeta:
    name: str = attr.ib()

    fields: dict[str, str] = attr.ib()
    subclass: set[str] = attr.ib()

@attr.s
class ComponentMeta:
    name: str = attr.ib()

    fields: dict[str, str] = attr.ib()
    subclass: set[str] = attr.ib()
    components: set[str] = attr.ib()

def walk_field(
    element: xml.etree.ElementTree.Element,
    field_map: dict[int, FieldMeta]
) -> None:
    number = int(element.attrib["number"])
    name = element.attrib["name"]
    typ = element.attrib["type"]

    f = FieldMeta(number, name, typ, [])
    assert f.number not in field_map, f"duplicated field number: {f} vs {field_map[f.number]}"
    for enum in element:
        if enum.tag == "value":
            value = enum.attrib["enum"]
            f.enums.append((value, enum.attrib["description"]))
        else:
            raise RuntimeError("not possible: field enums is nested...")

    field_map[f.number] = f

def walk_comp(
    element: xml.etree.ElementTree.Element,
    compes: dict[t.Tuple[t.Optional[str], str], ComponentMeta],
    ns: t.Optional[str]
) -> None:
    name = element.attrib["name"]
    c = ComponentMeta(name, {}, set(), set())
    assert (ns, c.name) not in compes, f"{(ns, c.name)} duplicated"
    compes[(ns, c.name)] = c

    for item in element:
        if item.tag == "field":
            c.fields[item.attrib["name"]] = item.attrib["required"]
        elif item.tag == "group":
            assert item.attrib["name"] not in c.subclass
            c.subclass.add(item.attrib["name"])
            walk_comp(item, compes, c.name if ns is None else ns)
        elif item.tag == "component":
            assert item.attrib["name"] not in c.components
            c.components.add(item.attrib["name"])
        else:
            raise RuntimeError(f"not possible for component, got tag: {item.tag}@{item.attrib}")

def expand_comp(
    c: t.Union[ClassMeta, SubClassMeta], comp: ComponentMeta,
    classes: dict[t.Tuple[t.Optional[str], str], t.Union[ClassMeta, SubClassMeta]],
    compes: dict[t.Tuple[t.Optional[str], str], ComponentMeta],
    ns: str
) -> None:
    for field in comp.fields:
        assert field not in c.fields
        c.fields[field] = comp.fields[field]

    for subclass in comp.subclass:
        sub_comp = compes[(comp.name, subclass)]
        assert subclass not in c.subclass
        c.subclass.add(subclass)

        t = SubClassMeta(subclass, {}, set())
        assert (ns, t.name) not in classes, f"component got class name conflicts: ({ns}, {t.name}) under {comp.name}"
        classes[(ns, t.name)] = t
        expand_comp(t, sub_comp, classes, compes, ns)

    for subcomp in comp.components:
        sub_comp = compes[(None, subcomp)]
        expand_comp(c, sub_comp, classes, compes, ns)

def walk_message(
    element: xml.etree.ElementTree.Element,
    classes: dict[t.Tuple[t.Optional[str], str], t.Union[ClassMeta, SubClassMeta]],
    ns: t.Optional[str],
    compes: dict[t.Tuple[t.Optional[str], str], ComponentMeta]
) -> None:
    name = element.attrib["name"]

    if ns is None:
        msgcat = element.attrib["msgcat"]
        msgtype = element.attrib["msgtype"]
        c: t.Union[SubClassMeta, ClassMeta] = ClassMeta(name, msgcat, msgtype, {}, set())
    else:
        c = SubClassMeta(name, {}, set())
    assert (ns, c.name) not in classes, f"{(ns, c.name)} duplicated..."
    classes[(ns, c.name)] = c

    for item in element:
        if item.tag == "field":
            c.fields[item.attrib["name"]] = item.attrib["required"]
        elif item.tag == "group":
            assert item.attrib["name"] not in c.subclass
            c.subclass.add(item.attrib["name"])
            walk_message(item, classes, c.name if ns is None else ns, compes)
        elif item.tag == "component":
            comp_name = item.attrib["name"]
            assert (None, comp_name) in compes, f"{comp_name} not in components"

            comp = compes[(None, comp_name)]
            expand_comp(c, comp, classes, compes, c.name if ns is None else ns)

            # assert item.attrib["name"] not in c.components
            # c.components.add(item.attrib["name"])
            # if item.attrib["required"] != "Y": print(f"illegal required tag for {item.attrib}")
        else:
            raise RuntimeError(f"not possible, got tag: {item.tag}@{item.attrib}")

def write_class_to_file(
    ns: str,
    tabnum: int,
    name: str,
    fields: dict[str, str],
    subclass: set[str],
    field_map: dict[str, FieldMeta],
    v_quickfix: str,
) -> str:
    tabs = " " * tabnum

    transforms = []
    if len(ns) > 0:
        transforms.append(f"m = {v_quickfix}.{ns}.{name}()")
    else:
        transforms.append(f"m = {v_quickfix}.{name}()")
    constructs1, constructs2 = [], []
    fields1_s, fields2_s = [], []
    for field, is_required in fields.items():
        assert is_required in ["Y", "N"]

        field_m = field_map[field]
        typeto = TYP_MAP[field_m.typ]

        typename = {
            str: "str",
            int: "int",
            float: "float",
            bool: "bool",
        }[typeto]

        typefun = {
            str: str,
            int: int,
            float: float,
            bool: lambda x: {"Y": True, "N": False}[x]
        }[typeto]
        if len(field_m.enums) > 0:
            # value must satisfy typefun
            [typefun(v) for (v, _) in field_m.enums] # type: ignore
            typename = "t.Literal[{}]".format(", ".join([repr(k) for k, _ in field_m.enums]))
        else:
            pass

        converter = {
            str: "str",
            int: "int",
            float: "float",
            bool: "_bool"
        }[typeto]

        # Dirty patch
        if field_m.typ == "UTCTIMESTAMP":
            transform_state = f"t = fix.{field_m.name}(); t.setString(self.{field_m.name}); m.setField(t) # noqa"
        else:
            transform_state = f"m.setField(fix.{field_m.name}(self.{field_m.name}))"

        if is_required == "Y":
            field_entry = f"{field}: {typename} = attr.ib(converter={converter})"
            fields1_s.append(field_entry)
            constructs1.append((
                field_m.name, f"{field_m.name} = m.getField({field_m.number})"
            ))
            transforms.append(transform_state)
        else:
            typename = f"t.Optional[{typename}]"
            field_entry = f"{field}: {typename} = attr.ib(default=None, converter=attr.converters.optional({converter}))"
            fields2_s.append(field_entry)
            constructs2.append((
                field_m.name,
                f"{field_m.name} = m.getField({field_m.number}) if m.isSetField({field_m.number}) else None"
            ))

            if field_m.typ == "UTCTIMESTAMP":
                transforms.append(f"if self.{field_m.name} is not None:")
                transforms.append(f"{tabs}{transform_state}")
            else:
                transforms.append(f"if self.{field_m.name} is not None: {transform_state}")

    subclass = list(subclass) # make order right
    constructs_subclass = []
    for sname in subclass:
        field_m = field_map[sname]
        _sname = f"_{sname}"

        constructs_subclass.append(f"{_sname} = []")
        constructs_subclass.append(f"g = {v_quickfix}.{name}.{sname}()")
        constructs_subclass.append(f"for idx in range(1, (m.getField({field_m.number}) if m.isSetField({field_m.number}) else 0) + 1):")
        constructs_subclass.append(f"{tabs}m.getGroup(idx, g)")
        constructs_subclass.append(f"{tabs}{_sname}.append({sname}.from_raw(g))")
        transforms.append(f"for f in self.{sname}: m.addGroup(f.to_raw())")

    fields_s = "\n".join([f"{tabs}{f}" for f in fields1_s+fields2_s])
    subclass_s = "\n".join([f"{tabs}{s}: list[{s}] = attr.ib(default=[])" for s in subclass])
    constructs_s = "\n".join([f"{tabs}{tabs}{c}" for _, c in constructs1+constructs2])
    constructs_subclass_s = "\n".join([f"{tabs}{tabs}{c}" for c in constructs_subclass])
    args = [c for c, _ in constructs1+constructs2] + [f"_{s}" for s in subclass] + ["raw"]
    assert len(args) == len(set(args)), "args duplicated"
    args_s = ", ".join(args)
    transforms_s = "\n".join([f"{tabs}{tabs}{f}" for f in transforms])
    if len(fields) + len(subclass) == 0: fields_s = f"{tabs}pass"
    return f"""@attr.s
class {name}:
{fields_s}
{subclass_s}
{tabs}raw: t.Optional[fix.Message] = attr.ib(default=None, repr=False)

{tabs}@classmethod
{tabs}def from_raw(cls, m: fix.Message) -> {name}:
{constructs_s}
{constructs_subclass_s}
{tabs}{tabs}raw = m
{tabs}{tabs}return cls({args_s})

{tabs}def to_raw(self) -> fix.Message:
{transforms_s}
{tabs}{tabs}return m
"""

def write_single_to_file(
    mc: ClassMeta,
    sc: dict[str, SubClassMeta],
    field_map: dict[str, FieldMeta],
    fname: str,
    v_major: int,
    v_minor: int,
    v_sp: int,
) -> None:
    print(f"writing to {fname}")
    v_quickfix = f"quickfix{v_major}{v_minor}" if v_sp == 0 else f"quickfix{v_major}{v_minor}sp{v_sp}"
    with open(fname, "w") as fh:
        classes = []

        consts = f"""MSGCAT: str = \"{mc.msgcat}\"
MSGTYPE: str = \"{mc.msgtype}\""""

        assert len(mc.name) > 0, "not possible"
        classes.append(
            write_class_to_file("", 4, mc.name, mc.fields, mc.subclass, field_map, v_quickfix)
        )

        for x in sc.values():
            classes.append(write_class_to_file(mc.name, 4, x.name, x.fields, x.subclass, field_map, v_quickfix))

        fh.write("""from __future__ import annotations
import typing as t # noqa
import quickfix as fix
import attr
import {}
from . import _bool

{}

{}""".format(v_quickfix, consts, "\n\n".join(classes)))

def write_init_to_file(
    fname: str, m_class_list: list[str],
    classes: dict[t.Tuple[t.Optional[str], str], t.Union[ClassMeta, SubClassMeta]],
    v_major: int, v_minor: int,
) -> None:
    print(f"writing init to {fname}")
    imports = ", ".join([m.lower() for m in m_class_list])
    imports = f"from . import {imports}" if len(m_class_list) > 0 else ""

    ns_imports = "\n".join([f"from .{m.lower()} import {m} as {m} # noqa" for m in m_class_list])
    # ns_imports = "\n".join([f"{m} = {m.lower()}.{m}" for m in m_class_list])

    msgtype_list = []
    for mc in m_class_list:
        m = classes[(None, mc)]
        assert isinstance(m, ClassMeta)
        msgtype_list.append(f"\"{m.msgtype}\": ({m.name}, \"on_fix{v_major}{v_minor}_{m.name}\")")

    msgtype_list_s = "\n".join([f"    {m}," for m in msgtype_list])

    with open(fname, "w") as fh:
        fh.write(f"""from __future__ import annotations
import typing as t # noqa
import quickfix as fix
def _bool(x: str) -> bool:
    return {{"Y": True, "N": False}}[x]

{imports} # noqa
{ns_imports}

BeginString: str = "FIX.{v_major}.{v_minor}"
MESSAGES: dict[str, t.Tuple[t.Any, str]] = {{
{msgtype_list_s}
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
""")

def write_to_file(
    classes: dict[t.Tuple[t.Optional[str], str], t.Union[ClassMeta, SubClassMeta]],
    field_map: dict[str, FieldMeta],
    dirname: str,
    v_major: int, v_minor: int, v_sp: int,
) -> None:
    print(f"saving to {dirname}")
    if not os.path.exists(dirname): os.makedirs(dirname)
    main_class = [k for (ns, k) in classes.keys() if ns is None]
    print(f"class: #{len(main_class)}")
    for classname in main_class:
        assert classname.lower() != classname, "Message class name in lower case, you have to find other way to make namespace right"
        fname = os.path.join(dirname, f"{classname.lower()}.py")
        m_class = classes[(None, classname)]
        s_class = {k: c for (ns, k), c in classes.items() if ns == classname}
        assert isinstance(m_class, ClassMeta)
        assert all(isinstance(v, SubClassMeta) for v in s_class.values())
        write_single_to_file(m_class, s_class, field_map, fname, v_major, v_minor, v_sp) # type: ignore

    write_init_to_file(os.path.join(dirname, "__init__.py"), main_class, classes, v_major, v_minor)

def write_module_init_file(
    modules: list[str],
    target_dir: str,
    lazy: bool = True,
) -> None:
    fname = os.path.join(target_dir, "__init__.py")
    print(f"writing module init to {fname}")
    with open(fname, "w") as fh:
        if len(modules) > 0:
            if not lazy:
                imports = ", ".join(modules)
                fh.write(f"from . import {imports} # noqa \n")
            else:
                pass

# https://stackoverflow.com/questions/49891378/when-do-we-use-fix50sp2-and-fixt11-xml
def main(spec_dir: str, target_dir: str) -> None:
    modules = []
    for v_major, v_minor, v_sp in [
            (4, 0, 0),
            (4, 1, 0),
            (4, 2, 0),
            (4, 3, 0),
            (4, 4, 0),
            (5, 0, 0),
            (5, 0, 1),
            (5, 0, 2),
    ]:
        _fname = f"FIX{v_major}{v_minor}.xml" if v_sp == 0 else f"FIX{v_major}{v_minor}SP{v_sp}.xml"
        fname = os.path.join(spec_dir, _fname)
        assert os.path.exists(fname), f"spec xml not found: {fname}"
        print(f"working on {fname}")

        doc = xml.etree.ElementTree.parse(fname)

        fields = doc.find("fields")
        assert fields is not None
        field_map: dict[int, FieldMeta] = {}
        for field in fields:
            assert field.tag == "field"
            walk_field(field, field_map)
        typ_u = set(f.typ for f in field_map.values())
        assert typ_u.issubset(set(TYP_MAP.keys())), "typ unknown: {}".format(typ_u.difference(set(TYP_MAP.keys())))
        # print(f"Type found: #{len(typ_u)}, {typ_u}")

        # components
        components = doc.find("components")
        assert components is not None
        compes: dict[t.Tuple[t.Optional[str], str], ComponentMeta] = {}
        for component in components:
            assert component.tag == "component"
            walk_comp(component, compes, None)

        # messages
        messages = doc.find("messages")
        assert messages is not None

        classes: dict[t.Tuple[t.Optional[str], str], t.Union[ClassMeta, SubClassMeta]] = {}
        for message in messages:
            assert message.tag == "message"
            walk_message(message, classes, None, compes)

        classes_u = list(c for c in classes.values() if isinstance(c, ClassMeta))
        assert len(set(c.msgtype for c in classes_u)) == len(classes_u), "msgtype not unique under this scheme"

        assert "Message" not in [k for _, k in classes.keys()]
        assert "MessageCracker" not in [k for _, k in classes.keys()]

        # print([v for v in field_map.values() if v.typ == "UTCTIMESTAMP"])

        module_name = os.path.splitext(os.path.basename(_fname))[0].lower()
        modules.append(module_name)
        write_to_file(
            classes,
            {v.name: v for v in field_map.values()},
            os.path.join(target_dir, module_name),
            v_major, v_minor, v_sp
        )

        # for k, v in classes.items():
        #     if k[0] is None: continue
        #     print(k, v)
    write_module_init_file(modules, target_dir)

if __name__ == "__main__":
    main("./spec/", "./spec")

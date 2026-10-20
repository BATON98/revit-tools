# -*- coding: utf-8 -*-
"""Общие функции для кнопок RevitTools (Revit 2027, pyRevit 7)."""
from __future__ import unicode_literals

import io
import os

import System
from pyrevit import DB, forms


# ---------------------------------------------------------------- ElementId

def eid_int(element_id):
    """ElementId -> int. В Revit 2024+ используется .Value (IntegerValue удалён в 2026+)."""
    try:
        return int(element_id.Value)
    except AttributeError:
        return int(element_id.IntegerValue)


def to_eid(number):
    """int/str -> ElementId (с Revit 2026 конструктор принимает Int64)."""
    return DB.ElementId(System.Int64(int(number)))


# ---------------------------------------------------------------- Имена

def get_name(element):
    """Безопасно получить имя элемента/типа."""
    try:
        return element.Name
    except Exception:
        try:
            return DB.Element.Name.GetValue(element)
        except Exception:
            return ""


def type_full_name(doc, element):
    """'Семейство : Тип' для экземпляра."""
    type_id = element.GetTypeId()
    if type_id is None or type_id == DB.ElementId.InvalidElementId:
        return ""
    el_type = doc.GetElement(type_id)
    if el_type is None:
        return ""
    family = getattr(el_type, "FamilyName", "") or ""
    name = get_name(el_type)
    return "{} : {}".format(family, name) if family else name


# ---------------------------------------------------------------- Параметры

YES_VALUES = ("да", "yes", "true", "1", "истина")
NO_VALUES = ("нет", "no", "false", "0", "ложь")


def param_value(param):
    """Значение параметра строкой (в единицах проекта)."""
    if param is None or not param.HasValue:
        return ""
    storage = param.StorageType
    if storage == DB.StorageType.String:
        return param.AsString() or ""
    if storage == DB.StorageType.Integer:
        value = param.AsValueString()
        return value if value is not None else str(param.AsInteger())
    # Double и ElementId — как отображает Revit
    return param.AsValueString() or ""


def set_param_value(param, text):
    """Записать строковое значение в параметр. Возвращает True при изменении."""
    if param is None or param.IsReadOnly:
        return False
    storage = param.StorageType
    if storage == DB.StorageType.String:
        return param.Set(text)
    if storage == DB.StorageType.Integer:
        low = text.strip().lower()
        if low in YES_VALUES:
            return param.Set(1)
        if low in NO_VALUES:
            return param.Set(0)
        try:
            return param.Set(int(low))
        except ValueError:
            return param.SetValueString(text)
    if storage == DB.StorageType.Double:
        return param.SetValueString(text)
    return False  # ElementId-параметры не меняем из текста


def instance_param_names(elements, limit=200):
    """Имена параметров экземпляров (по первым limit элементам)."""
    names = set()
    for element in list(elements)[:limit]:
        for param in element.Parameters:
            names.add(param.Definition.Name)
    return sorted(names)


def is_empty(param):
    return param is None or param_value(param).strip() == ""


# ---------------------------------------------------------------- Категории

def model_instances(doc):
    """Все экземпляры модели, у которых есть категория."""
    collector = DB.FilteredElementCollector(doc).WhereElementIsNotElementType()
    return [el for el in collector if el.Category is not None]


def pick_category_elements(doc, title="Выберите категорию"):
    """Диалог выбора категории. Возвращает (имя_категории, [элементы]) или (None, [])."""
    by_category = {}
    for element in model_instances(doc):
        cat = element.Category
        if cat.CategoryType != DB.CategoryType.Model and cat.Name not in ("Помещения", "Rooms", "Листы", "Sheets"):
            continue
        by_category.setdefault(cat.Name, []).append(element)
    if not by_category:
        return None, []
    options = ["{}  ({})".format(name, len(items)) for name, items in sorted(by_category.items())]
    choice = forms.SelectFromList.show(options, title=title, button_name="Выбрать")
    if not choice:
        return None, []
    name = choice.rsplit("  (", 1)[0]
    return name, by_category[name]


# ---------------------------------------------------------------- CSV (Excel)

def _csv_cell(value):
    text = "" if value is None else "{}".format(value)
    if any(ch in text for ch in (";", '"', "\n", "\r")):
        text = '"' + text.replace('"', '""') + '"'
    return text


def write_csv(path, header, rows):
    """CSV с разделителем ';' и BOM — открывается в русском Excel без настроек."""
    with io.open(path, "w", encoding="utf-8-sig", newline="") as stream:
        stream.write(";".join(_csv_cell(h) for h in header) + "\r\n")
        for row in rows:
            stream.write(";".join(_csv_cell(v) for v in row) + "\r\n")


def _split_csv_line(line, delimiter):
    cells, current, quoted, i = [], [], False, 0
    while i < len(line):
        ch = line[i]
        if quoted:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    current.append('"')
                    i += 1
                else:
                    quoted = False
            else:
                current.append(ch)
        elif ch == '"':
            quoted = True
        elif ch == delimiter:
            cells.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    cells.append("".join(current))
    return cells


def read_csv(path):
    """Прочитать CSV (UTF-8 или Windows-1251, разделитель ';' или ',').

    Возвращает (заголовок, [строки]). Пустые строки пропускаются.
    """
    text = None
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            with io.open(path, "r", encoding=encoding) as stream:
                text = stream.read()
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Не удалось прочитать файл: неизвестная кодировка")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [], []
    delimiter = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    rows = [[c.strip() for c in _split_csv_line(ln, delimiter)] for ln in lines]
    return rows[0], rows[1:]


def default_csv_path(doc, suffix):
    """Предложенное имя файла рядом с моделью (или в Документах)."""
    base = os.path.splitext(os.path.basename(doc.PathName or ""))[0] or doc.Title
    return "{}_{}.csv".format(base, suffix)


def ask_save_csv(doc, suffix):
    return forms.save_file(file_ext="csv", default_name=default_csv_path(doc, suffix))


def open_file(path):
    """Открыть файл в программе по умолчанию (Excel)."""
    try:
        os.startfile(path)
    except Exception:
        pass

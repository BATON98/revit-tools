# -*- coding: utf-8 -*-
"""Создание листов из Excel (CSV): колонки «Номер» и «Название»."""
from __future__ import unicode_literals

from pyrevit import revit, DB, forms, script

from rt_utils import get_name, read_csv, write_csv, open_file

doc = revit.doc
output = script.get_output()
output.set_title("Листы из Excel")

TEMPLATE = "Сохранить шаблон CSV"
CREATE = "Создать листы из CSV"

action = forms.CommandSwitchWindow.show([CREATE, TEMPLATE], message="Что сделать?")
if not action:
    script.exit()

if action == TEMPLATE:
    path = forms.save_file(file_ext="csv", default_name="листы_шаблон.csv")
    if path:
        write_csv(path, ["Номер", "Название"], [["А-101", "План 1 этажа"], ["А-102", "План 2 этажа"],
                                                 ["А-201", "Фасады"], ["А-301", "Разрезы"]])
        open_file(path)
    script.exit()

path = forms.pick_file(file_ext="csv", title="CSV со списком листов")
if not path:
    script.exit()

header, rows = read_csv(path)
lower = [h.strip().lower() for h in header]
try:
    num_col = next(i for i, h in enumerate(lower) if h in ("номер", "number", "номер листа", "sheet number"))
    name_col = next(i for i, h in enumerate(lower) if h in ("название", "имя", "name", "имя листа", "sheet name"))
except StopIteration:
    forms.alert("В файле нужны колонки «Номер» и «Название».\n"
                "Сохраните шаблон этой же кнопкой и заполните его.", title="Неверный файл")
    script.exit()

title_blocks = list(DB.FilteredElementCollector(doc)
                    .OfCategory(DB.BuiltInCategory.OST_TitleBlocks)
                    .WhereElementIsElementType())
options = {"Без основной надписи": DB.ElementId.InvalidElementId}
for tb in title_blocks:
    options["{} : {}".format(tb.FamilyName, get_name(tb))] = tb.Id
choice = forms.SelectFromList.show(sorted(options.keys()), title="Основная надпись для новых листов",
                                   button_name="Выбрать")
if not choice:
    script.exit()
title_block_id = options[choice]

existing = set(s.SheetNumber for s in DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet))
created, skipped = [], []
with revit.Transaction("RevitTools: листы из CSV"):
    for row in rows:
        number = row[num_col] if num_col < len(row) else ""
        name = row[name_col] if name_col < len(row) else ""
        if not number:
            continue
        if number in existing:
            skipped.append([number, name, "лист с таким номером уже есть"])
            continue
        try:
            sheet = DB.ViewSheet.Create(doc, title_block_id)
            sheet.SheetNumber = number
            if name:
                sheet.Name = name
            existing.add(number)
            created.append([output.linkify(sheet.Id), number, name])
        except Exception as error:
            skipped.append([number, name, str(error)])

output.print_md("# Создано листов: {}".format(len(created)))
if created:
    output.print_table(created, columns=["Лист", "Номер", "Название"])
if skipped:
    output.print_table(skipped, columns=["Номер", "Название", "Причина"], title="Пропущено")

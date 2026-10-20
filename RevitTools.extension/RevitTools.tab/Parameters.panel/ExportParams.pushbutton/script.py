# -*- coding: utf-8 -*-
"""Выгрузка параметров элементов в Excel (CSV). Файл потом можно отредактировать и загрузить обратно."""
from __future__ import unicode_literals

from pyrevit import revit, forms, script

from rt_utils import (eid_int, param_value, type_full_name, instance_param_names,
                      pick_category_elements, ask_save_csv, write_csv, open_file)

doc = revit.doc
output = script.get_output()

selection = revit.get_selection().elements
elements = []
if selection and forms.alert("Выгрузить только выделенные элементы ({} шт.)?".format(len(selection)),
                             yes=True, no=True, title="Экспорт параметров"):
    elements = list(selection)
else:
    _, elements = pick_category_elements(doc, "Экспорт параметров: выберите категорию")
if not elements:
    script.exit()

names = forms.SelectFromList.show(
    instance_param_names(elements),
    title="Какие параметры выгрузить?",
    multiselect=True,
    button_name="Выгрузить",
)
if not names:
    script.exit()

path = ask_save_csv(doc, "параметры")
if not path:
    script.exit()

header = ["ElementId", "Категория", "Тип"] + list(names)
rows = []
for element in elements:
    row = [eid_int(element.Id), element.Category.Name if element.Category else "", type_full_name(doc, element)]
    row.extend(param_value(element.LookupParameter(name)) for name in names)
    rows.append(row)

write_csv(path, header, rows)
output.print_md("**Выгружено {} элементов, {} параметров:** `{}`".format(len(rows), len(names), path))
output.print_md("_Отредактируйте значения в Excel, сохраните как CSV и загрузите кнопкой «Импорт параметров». "
                "Колонки ElementId, Категория и Тип не меняйте._")
open_file(path)

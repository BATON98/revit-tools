# -*- coding: utf-8 -*-
"""Все предупреждения модели: группировка по тексту, выделение элементов, экспорт в Excel (CSV)."""
from __future__ import unicode_literals

from collections import OrderedDict

from pyrevit import revit, DB, forms, script

from rt_utils import eid_int, ask_save_csv, write_csv, open_file

doc = revit.doc
output = script.get_output()
output.set_title("Предупреждения")

warnings = doc.GetWarnings()
if not warnings:
    forms.alert("В модели нет предупреждений. Отлично!", title="Предупреждения")
    script.exit()

grouped = OrderedDict()
for warning in warnings:
    grouped.setdefault(warning.GetDescriptionText(), []).append(warning)
grouped = OrderedDict(sorted(grouped.items(), key=lambda item: -len(item[1])))

output.print_md("# Предупреждения: {} шт., {} видов".format(len(warnings), len(grouped)))
output.print_md("_Нажмите на ссылку с ID, чтобы выделить элементы в модели._")

for text, items in grouped.items():
    output.print_md("### {} — {} шт.".format(text, len(items)))
    all_ids = []
    for warning in items:
        all_ids.extend(warning.GetFailingElements())
        all_ids.extend(warning.GetAdditionalElements())
    if all_ids:
        print("Выделить все элементы группы: {}".format(output.linkify(list(set(all_ids)))))

if forms.alert("Сохранить полный список предупреждений в Excel (CSV)?", yes=True, no=True, title="Экспорт"):
    path = ask_save_csv(doc, "предупреждения")
    if path:
        rows = []
        for number, warning in enumerate(warnings, 1):
            failing = [eid_int(i) for i in warning.GetFailingElements()]
            additional = [eid_int(i) for i in warning.GetAdditionalElements()]
            categories = set()
            for element_id in list(warning.GetFailingElements()) + list(warning.GetAdditionalElements()):
                element = doc.GetElement(element_id)
                if element is not None and element.Category is not None:
                    categories.add(element.Category.Name)
            rows.append([
                number,
                warning.GetDescriptionText(),
                "Ошибка" if warning.GetSeverity() == DB.FailureSeverity.Error else "Предупреждение",
                ", ".join(str(i) for i in failing),
                ", ".join(str(i) for i in additional),
                ", ".join(sorted(categories)),
            ])
        write_csv(path, ["№", "Текст", "Тип", "ID элементов", "ID доп. элементов", "Категории"], rows)
        output.print_md("**Сохранено:** `{}`".format(path))
        open_file(path)

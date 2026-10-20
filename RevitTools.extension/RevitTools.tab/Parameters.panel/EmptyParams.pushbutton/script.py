# -*- coding: utf-8 -*-
"""Поиск элементов с незаполненными параметрами (проверка данных перед выдачей)."""
from __future__ import unicode_literals

from pyrevit import revit, forms, script

from rt_utils import is_empty, type_full_name, instance_param_names, pick_category_elements

doc = revit.doc
output = script.get_output()
output.set_title("Пустые параметры")

category, elements = pick_category_elements(doc, "Проверка параметров: выберите категорию")
if not elements:
    script.exit()

names = forms.SelectFromList.show(
    instance_param_names(elements),
    title="Какие параметры должны быть заполнены?",
    multiselect=True,
    button_name="Проверить",
)
if not names:
    script.exit()

output.print_md("# Проверка: {} ({} элементов)".format(category, len(elements)))

summary = []
all_bad = set()
for name in names:
    bad = [el for el in elements if is_empty(el.LookupParameter(name))]
    filled = len(elements) - len(bad)
    percent = 100.0 * filled / len(elements)
    mark = "🟢" if not bad else ("🟡" if percent >= 80 else "🔴")
    summary.append([mark, name, "{} из {}".format(filled, len(elements)), "{:.0f}%".format(percent),
                    output.linkify([el.Id for el in bad]) if bad else ""])
    all_bad.update(el.Id for el in bad)

output.print_table(summary, columns=["", "Параметр", "Заполнено", "%", "Выделить пустые"], title="Итог")

if all_bad:
    print("Выделить все элементы с пропусками ({} шт.): {}".format(len(all_bad), output.linkify(list(all_bad))))
    rows = []
    for element in elements:
        if element.Id not in all_bad:
            continue
        missing = [name for name in names if is_empty(element.LookupParameter(name))]
        rows.append([output.linkify(element.Id), type_full_name(doc, element), ", ".join(missing)])
        if len(rows) >= 500:
            break
    output.print_table(rows, columns=["Элемент", "Тип", "Не заполнено"],
                       title="Подробно (первые 500)" if len(rows) >= 500 else "Подробно")
else:
    output.print_md("✅ **Все выбранные параметры заполнены у всех элементов.**")

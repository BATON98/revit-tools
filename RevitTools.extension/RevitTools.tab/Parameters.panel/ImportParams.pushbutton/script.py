# -*- coding: utf-8 -*-
"""Загрузка значений параметров из Excel (CSV), выгруженного кнопкой «Экспорт параметров»."""
from __future__ import unicode_literals

from pyrevit import revit, forms, script

from rt_utils import to_eid, param_value, set_param_value, read_csv

doc = revit.doc
output = script.get_output()
output.set_title("Импорт параметров")

SERVICE_COLUMNS = ("elementid", "категория", "тип")

path = forms.pick_file(file_ext="csv", title="Выберите CSV с параметрами")
if not path:
    script.exit()

header, rows = read_csv(path)
if not header or header[0].strip().lower() != "elementid":
    forms.alert("Первая колонка файла должна называться ElementId.\n"
                "Сначала выгрузите файл кнопкой «Экспорт параметров».", title="Неверный файл")
    script.exit()

param_columns = [(i, name) for i, name in enumerate(header) if name.strip().lower() not in SERVICE_COLUMNS]

changes = []   # (element, param, old, new)
problems = []  # (id, параметр, причина)
for row in rows:
    raw_id = row[0].strip() if row else ""
    if not raw_id:
        continue
    try:
        element = doc.GetElement(to_eid(raw_id))
    except ValueError:
        element = None
    if element is None:
        problems.append([raw_id, "", "элемент не найден в модели"])
        continue
    for index, name in param_columns:
        new_value = row[index] if index < len(row) else ""
        param = element.LookupParameter(name)
        if param is None:
            problems.append([raw_id, name, "нет такого параметра у элемента"])
            continue
        old_value = param_value(param)
        if old_value == new_value:
            continue
        if param.IsReadOnly:
            problems.append([raw_id, name, "параметр только для чтения"])
            continue
        changes.append((element, param, old_value, new_value))

if not changes:
    forms.alert("Изменений нет: значения в файле совпадают с моделью.", title="Импорт параметров")
    if problems:
        output.print_table(problems, columns=["ElementId", "Параметр", "Причина"], title="Пропущено")
    script.exit()

if not forms.alert("Будет изменено значений: {}. Продолжить?".format(len(changes)),
                   yes=True, no=True, title="Импорт параметров"):
    script.exit()

done = []
with revit.Transaction("RevitTools: импорт параметров"):
    for element, param, old_value, new_value in changes:
        try:
            ok = set_param_value(param, new_value)
        except Exception as error:
            ok, reason = False, str(error)
        else:
            reason = "Revit не принял значение"
        if ok:
            done.append([output.linkify(element.Id), param.Definition.Name, old_value, new_value])
        else:
            problems.append([str(element.Id), param.Definition.Name, "{} ({})".format(reason, new_value)])

output.print_md("# Изменено значений: {}".format(len(done)))
if done:
    output.print_table(done, columns=["Элемент", "Параметр", "Было", "Стало"])
if problems:
    output.print_table(problems, columns=["ElementId", "Параметр", "Причина"], title="Пропущено")

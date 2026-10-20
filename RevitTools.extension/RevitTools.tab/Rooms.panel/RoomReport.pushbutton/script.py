# -*- coding: utf-8 -*-
"""Отчёт по помещениям: площади по уровням и отделам, проблемные помещения, дубли номеров, экспорт в Excel."""
from __future__ import unicode_literals

from collections import Counter, OrderedDict

from pyrevit import revit, DB, forms, script

from rt_utils import eid_int, ask_save_csv, write_csv, open_file

doc = revit.doc
output = script.get_output()
output.set_title("Отчёт по помещениям")


def sqm(value):
    return DB.UnitUtils.ConvertFromInternalUnits(value, DB.UnitTypeId.SquareMeters)


def text_param(room, bip):
    param = room.get_Parameter(bip)
    return (param.AsString() or "") if param else ""


rooms = list(DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType())
if not rooms:
    forms.alert("В модели нет помещений.", title="Помещения")
    script.exit()

placed = [r for r in rooms if r.Location is not None and r.Area > 0]
unplaced = [r for r in rooms if r.Location is None]
unbounded = [r for r in rooms if r.Location is not None and r.Area == 0]

by_level = OrderedDict()
by_department = Counter()
count_department = Counter()
for room in sorted(placed, key=lambda r: (r.Level.Elevation if r.Level else 0)):
    level = room.Level.Name if room.Level else "—"
    area = sqm(room.Area)
    count, total = by_level.get(level, (0, 0.0))
    by_level[level] = (count + 1, total + area)
    dep = text_param(room, DB.BuiltInParameter.ROOM_DEPARTMENT) or "(не указан)"
    by_department[dep] += area
    count_department[dep] += 1

total_area = sum(sqm(r.Area) for r in placed)
output.print_md("# Помещения: {} шт., общая площадь {:.2f} м²".format(len(placed), total_area))

output.print_table(
    [[level, count, "{:.2f}".format(area)] for level, (count, area) in by_level.items()]
    + [["Итого", len(placed), "{:.2f}".format(total_area)]],
    columns=["Уровень", "Кол-во", "Площадь, м²"], title="По уровням",
)
output.print_table(
    [[dep, count_department[dep], "{:.2f}".format(area), "{:.1f}%".format(100.0 * area / total_area if total_area else 0)]
     for dep, area in by_department.most_common()],
    columns=["Отдел (Department)", "Кол-во", "Площадь, м²", "Доля"], title="По отделам",
)

numbers = Counter(r.Number for r in placed)
duplicates = [r for r in placed if numbers[r.Number] > 1]
if duplicates:
    output.print_table(
        [[output.linkify(r.Id), r.Number, text_param(r, DB.BuiltInParameter.ROOM_NAME), r.Level.Name if r.Level else ""]
         for r in sorted(duplicates, key=lambda x: x.Number)],
        columns=["ID", "Номер", "Имя", "Уровень"], title="⚠ Повторяющиеся номера",
    )

no_name = [r for r in placed if not text_param(r, DB.BuiltInParameter.ROOM_NAME).strip()]
problems = ([[output.linkify(r.Id), r.Number, "Не размещено (удалите или разместите)"] for r in unplaced]
            + [[output.linkify(r.Id), r.Number, "Не замкнуто или избыточно — проверьте границы"] for r in unbounded]
            + [[output.linkify(r.Id), r.Number, "Нет имени"] for r in no_name])
if problems:
    output.print_table(problems, columns=["ID", "Номер", "Проблема"], title="⚠ Проблемные помещения")
else:
    output.print_md("✅ **Проблемных помещений нет.**")

if forms.alert("Сохранить список помещений в Excel (CSV)?", yes=True, no=True, title="Экспорт"):
    path = ask_save_csv(doc, "помещения")
    if path:
        rows = []
        for room in sorted(rooms, key=lambda r: r.Number):
            rows.append([
                eid_int(room.Id),
                room.Number,
                text_param(room, DB.BuiltInParameter.ROOM_NAME),
                room.Level.Name if room.Level else "",
                text_param(room, DB.BuiltInParameter.ROOM_DEPARTMENT),
                "{:.2f}".format(sqm(room.Area)).replace(".", ","),
                "Не размещено" if room.Location is None else ("Не замкнуто" if room.Area == 0 else ""),
            ])
        write_csv(path, ["ElementId", "Номер", "Имя", "Уровень", "Отдел", "Площадь, м²", "Проблема"], rows)
        output.print_md("**Сохранено:** `{}`".format(path))
        open_file(path)

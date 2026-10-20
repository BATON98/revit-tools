# -*- coding: utf-8 -*-
"""Отчёт о здоровье модели: предупреждения, семейства, виды, импорт CAD, группы."""
from __future__ import unicode_literals

import os
from collections import Counter

from pyrevit import revit, DB, script

from rt_utils import get_name

doc = revit.doc
output = script.get_output()
output.set_title("Аудит модели")


def collect(cls=None, category=None, types=False):
    collector = DB.FilteredElementCollector(doc)
    if cls is not None:
        collector = collector.OfClass(cls)
    if category is not None:
        collector = collector.OfCategory(category)
    if types:
        return list(collector.WhereElementIsElementType())
    return list(collector.WhereElementIsNotElementType())


def status(value, warn, bad):
    """Цветовая метка: зелёный / жёлтый / красный."""
    if value >= bad:
        return "🔴"
    if value >= warn:
        return "🟡"
    return "🟢"


# ------------------------------------------------------------- Сбор данных
warnings = doc.GetWarnings()
instances = [el for el in collect() if el.Category is not None]
families = list(DB.FilteredElementCollector(doc).OfClass(DB.Family))
family_instances = list(DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance))
in_place = [fi for fi in family_instances if fi.Symbol.Family.IsInPlace]

used_family_ids = set(fi.Symbol.Family.Id for fi in family_instances)
editable_families = [f for f in families if f.IsEditable and not f.IsInPlace]
# Семейства без размещённых экземпляров (марки/основные надписи учитываются отдельно — только модельные)
unused_families = [
    f for f in editable_families
    if f.Id not in used_family_ids
    and f.FamilyCategory is not None
    and f.FamilyCategory.CategoryType == DB.CategoryType.Model
]

views = [v for v in DB.FilteredElementCollector(doc).OfClass(DB.View) if not v.IsTemplate]
templates = [v for v in DB.FilteredElementCollector(doc).OfClass(DB.View) if v.IsTemplate]
sheets = [v for v in views if isinstance(v, DB.ViewSheet)]
placed = set()
for sheet in sheets:
    placed.update(sheet.GetAllPlacedViews())
for ssi in DB.FilteredElementCollector(doc).OfClass(DB.ScheduleSheetInstance):
    placed.add(ssi.ScheduleId)

SKIP_VIEW_TYPES = (DB.ViewType.DrawingSheet, DB.ViewType.ProjectBrowser,
                   DB.ViewType.SystemBrowser, DB.ViewType.Internal, DB.ViewType.Undefined)
not_on_sheets = []
for view in views:
    if view.ViewType in SKIP_VIEW_TYPES or view.Id in placed:
        continue
    if isinstance(view, DB.ViewSchedule) and (view.IsTitleblockRevisionSchedule or view.IsInternalKeynoteSchedule):
        continue
    not_on_sheets.append(view)

imports = list(DB.FilteredElementCollector(doc).OfClass(DB.ImportInstance))
cad_imported = [i for i in imports if not i.IsLinked]
cad_linked = [i for i in imports if i.IsLinked]
rvt_links = list(DB.FilteredElementCollector(doc).OfClass(DB.RevitLinkInstance))
groups = collect(cls=DB.Group)
group_types = list(DB.FilteredElementCollector(doc).OfClass(DB.GroupType))
unused_group_types = [g for g in group_types if g.Groups.Size == 0]

rooms = collect(category=DB.BuiltInCategory.OST_Rooms)
unplaced_rooms = [r for r in rooms if r.Location is None]
unbounded_rooms = [r for r in rooms if r.Location is not None and r.Area == 0]

file_size_mb = None
if doc.PathName and os.path.exists(doc.PathName):
    file_size_mb = os.path.getsize(doc.PathName) / 1024.0 / 1024.0

# ------------------------------------------------------------- Сводка
output.print_md("# Аудит модели: {}".format(doc.Title))
output.print_md("_Чем больше красных и жёлтых пунктов, тем сильнее модель нуждается в чистке._")

summary = [
    [status(len(warnings), 100, 500), "Предупреждения", len(warnings)],
    [status(len(in_place), 10, 50), "Модели «по месту» (In-Place)", len(in_place)],
    [status(len(unused_families), 20, 100), "Неиспользуемые модельные семейства", len(unused_families)],
    [status(len(not_on_sheets), 50, 200), "Виды не на листах", len(not_on_sheets)],
    [status(len(cad_imported), 1, 10), "Импортированные CAD (не связи)", len(cad_imported)],
    [status(len(unused_group_types), 5, 20), "Неиспользуемые типы групп", len(unused_group_types)],
    [status(len(unplaced_rooms) + len(unbounded_rooms), 1, 10), "Неразмещённые / незамкнутые помещения",
     len(unplaced_rooms) + len(unbounded_rooms)],
    ["ℹ️", "Элементов в модели", len(instances)],
    ["ℹ️", "Семейств загружено", len(families)],
    ["ℹ️", "Видов / шаблонов / листов", "{} / {} / {}".format(len(views), len(templates), len(sheets))],
    ["ℹ️", "Связи RVT / связи CAD", "{} / {}".format(len(rvt_links), len(cad_linked))],
    ["ℹ️", "Экземпляров групп", len(groups)],
    ["ℹ️", "Совместная работа (worksharing)", "Да" if doc.IsWorkshared else "Нет"],
]
if file_size_mb is not None:
    summary.append([status(file_size_mb, 300, 800), "Размер файла, МБ", round(file_size_mb, 1)])

output.print_table(summary, columns=["", "Показатель", "Значение"], title="Сводка")

# ------------------------------------------------------------- Детали
if warnings:
    by_text = Counter(w.GetDescriptionText() for w in warnings)
    output.print_table(
        [[count, text] for text, count in by_text.most_common(15)],
        columns=["Кол-во", "Текст предупреждения"],
        title="Топ-15 предупреждений (полный список — кнопка «Предупреждения»)",
    )

by_category = Counter(el.Category.Name for el in instances)
output.print_table(
    [[name, count] for name, count in by_category.most_common(20)],
    columns=["Категория", "Кол-во"],
    title="Топ-20 категорий по числу элементов",
)

if in_place:
    rows = [[output.linkify(fi.Id), fi.Symbol.Family.Name, fi.Category.Name if fi.Category else ""]
            for fi in in_place]
    output.print_table(rows, columns=["ID", "Семейство", "Категория"], title="Модели «по месту»")

if cad_imported:
    rows = [[output.linkify(i.Id), get_name(doc.GetElement(i.GetTypeId())),
             get_name(doc.GetElement(i.OwnerViewId)) if i.OwnerViewId != DB.ElementId.InvalidElementId else "3D / модель"]
            for i in cad_imported]
    output.print_table(rows, columns=["ID", "Файл", "Вид"], title="Импортированные CAD — лучше заменить на связи")

if unused_families:
    rows = [[f.Name, f.FamilyCategory.Name] for f in sorted(unused_families, key=lambda x: x.Name)]
    output.print_table(rows, columns=["Семейство", "Категория"],
                       title="Неиспользуемые модельные семейства (удалить: Управление → Удалить неиспользуемое)")

if unplaced_rooms or unbounded_rooms:
    rows = [[output.linkify(r.Id), r.Number, r.get_Parameter(DB.BuiltInParameter.ROOM_NAME).AsString(),
             "Не размещено" if r.Location is None else "Не замкнуто / избыточно"]
            for r in unplaced_rooms + unbounded_rooms]
    output.print_table(rows, columns=["ID", "Номер", "Имя", "Проблема"], title="Проблемные помещения")

output.print_md("---\nВиды не на листах можно удалить кнопкой **«Виды без листов»**.")

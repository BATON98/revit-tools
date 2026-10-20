# -*- coding: utf-8 -*-
"""Виды, не размещённые на листах: список и удаление выбранных."""
from __future__ import unicode_literals

from pyrevit import revit, DB, forms, script

doc = revit.doc
output = script.get_output()
output.set_title("Виды без листов")

SKIP_VIEW_TYPES = (DB.ViewType.DrawingSheet, DB.ViewType.ProjectBrowser,
                   DB.ViewType.SystemBrowser, DB.ViewType.Internal, DB.ViewType.Undefined)

VIEW_TYPE_NAMES = {
    DB.ViewType.FloorPlan: "План этажа",
    DB.ViewType.CeilingPlan: "План потолка",
    DB.ViewType.EngineeringPlan: "План несущих конструкций",
    DB.ViewType.AreaPlan: "План зон",
    DB.ViewType.Elevation: "Фасад",
    DB.ViewType.Section: "Разрез",
    DB.ViewType.Detail: "Узел",
    DB.ViewType.ThreeD: "3D",
    DB.ViewType.DraftingView: "Чертёжный вид",
    DB.ViewType.Legend: "Легенда",
    DB.ViewType.Schedule: "Спецификация",
    DB.ViewType.Walkthrough: "Обход",
    DB.ViewType.Rendering: "Визуализация",
}


class ViewItem(forms.TemplateListItem):
    @property
    def name(self):
        view = self.item
        kind = VIEW_TYPE_NAMES.get(view.ViewType, str(view.ViewType))
        return "[{}]  {}".format(kind, view.Name)


placed = set()
for sheet in DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet):
    placed.update(sheet.GetAllPlacedViews())
for ssi in DB.FilteredElementCollector(doc).OfClass(DB.ScheduleSheetInstance):
    placed.add(ssi.ScheduleId)

candidates = []
for view in DB.FilteredElementCollector(doc).OfClass(DB.View):
    if view.IsTemplate or view.ViewType in SKIP_VIEW_TYPES or view.Id in placed:
        continue
    if isinstance(view, DB.ViewSchedule) and (view.IsTitleblockRevisionSchedule or view.IsInternalKeynoteSchedule):
        continue
    if view.ViewType == DB.ViewType.ThreeD and view.Name in ("{3D}", "{3D - " + doc.Application.Username + "}"):
        continue  # служебный 3D-вид
    candidates.append(view)

if not candidates:
    forms.alert("Все виды размещены на листах.", title="Виды без листов")
    script.exit()

candidates.sort(key=lambda v: (str(v.ViewType), v.Name))
selected = forms.SelectFromList.show(
    [ViewItem(v) for v in candidates],
    title="Виды без листов: {} шт. Отметьте, какие удалить".format(len(candidates)),
    multiselect=True,
    button_name="Удалить отмеченные",
)
if not selected:
    script.exit()

if not forms.alert("Удалить {} видов? Это можно отменить через Ctrl+Z.".format(len(selected)),
                   yes=True, no=True, title="Подтверждение"):
    script.exit()

active_id = doc.ActiveView.Id
deleted, failed = [], []
with revit.Transaction("RevitTools: удаление видов без листов"):
    for view in selected:
        if not view.IsValidObject:
            continue  # уже удалён вместе с родительским видом
        if view.Id == active_id:
            failed.append((view.Name, "это активный вид — переключитесь на другой"))
            continue
        name = view.Name
        try:
            doc.Delete(view.Id)
            deleted.append(name)
        except Exception as error:
            failed.append((name, str(error)))

output.print_md("# Удалено видов: {}".format(len(deleted)))
for name in deleted:
    print("✔ {}".format(name))
if failed:
    output.print_table([list(f) for f in failed], columns=["Вид", "Причина"], title="Не удалось удалить")

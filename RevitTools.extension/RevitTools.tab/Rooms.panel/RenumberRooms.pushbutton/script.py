# -*- coding: utf-8 -*-
"""Перенумерация помещений щелчками по порядку. Esc — закончить."""
from __future__ import unicode_literals

import re

from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import revit, DB, forms, script

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()
output.set_title("Перенумерация помещений")


class RoomFilter(ISelectionFilter):
    def AllowElement(self, element):
        return element.Category is not None and element.Category.BuiltInCategory == DB.BuiltInCategory.OST_Rooms

    def AllowReference(self, reference, point):
        return False


start = forms.ask_for_string(
    default="101",
    prompt="Первый номер. Можно с префиксом: «101», «А-01», «2.001».\n"
           "Последнее число в номере будет увеличиваться на 1.",
    title="Перенумерация помещений",
)
if not start:
    script.exit()

match = re.match(r"^(.*?)(\d+)(\D*)$", start)
if not match:
    forms.alert("В номере должно быть число, например 101 или А-01.", title="Перенумерация")
    script.exit()
prefix, digits, suffix = match.groups()
counter = int(digits)
width = len(digits)

taken = {}
for room in DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType():
    taken[room.Number] = room

done = []
room_filter = RoomFilter()
while True:
    number = "{}{}{}".format(prefix, str(counter).zfill(width), suffix)
    try:
        reference = uidoc.Selection.PickObject(
            ObjectType.Element, room_filter,
            "Щёлкните помещение для номера {} (Esc — закончить)".format(number))
    except OperationCanceledException:
        break
    room = doc.GetElement(reference.ElementId)
    old_number = room.Number
    with revit.Transaction("RevitTools: номер помещения {}".format(number)):
        other = taken.get(number)
        # Если номер занят другим помещением — меняем их местами, чтобы не было дублей
        if other is not None and other.Id != room.Id and other.IsValidObject:
            other.Number = old_number
            taken[old_number] = other
            done.append([output.linkify(other.Id), number, old_number, "обмен номерами"])
        elif old_number in taken and taken[old_number].Id == room.Id:
            del taken[old_number]
        room.Number = number
        taken[number] = room
    done.append([output.linkify(room.Id), old_number, number, ""])
    counter += 1

if done:
    output.print_md("# Перенумеровано помещений: {}".format(len(done)))
    output.print_table(done, columns=["Помещение", "Было", "Стало", "Примечание"])

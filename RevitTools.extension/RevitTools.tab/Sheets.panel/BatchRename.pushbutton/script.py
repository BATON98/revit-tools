# -*- coding: utf-8 -*-
"""Пакетное переименование видов, листов, уровней и типов семейств: найти/заменить, префикс, суффикс, регистр."""
from __future__ import unicode_literals

from pyrevit import revit, DB, forms, script

from rt_utils import get_name

doc = revit.doc
output = script.get_output()
output.set_title("Пакетное переименование")


def views():
    return [v for v in DB.FilteredElementCollector(doc).OfClass(DB.View)
            if not v.IsTemplate and not isinstance(v, DB.ViewSheet)
            and v.ViewType not in (DB.ViewType.ProjectBrowser, DB.ViewType.SystemBrowser, DB.ViewType.Internal)]


TARGETS = [
    ("Виды", views),
    ("Шаблоны видов", lambda: [v for v in DB.FilteredElementCollector(doc).OfClass(DB.View) if v.IsTemplate]),
    ("Листы (название)", lambda: list(DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet))),
    ("Уровни", lambda: list(DB.FilteredElementCollector(doc).OfClass(DB.Level))),
    ("Типы семейств", lambda: list(DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol))),
    ("Семейства", lambda: [f for f in DB.FilteredElementCollector(doc).OfClass(DB.Family) if f.IsEditable]),
]


class NamedItem(forms.TemplateListItem):
    @property
    def name(self):
        element = self.item
        if isinstance(element, DB.ViewSheet):
            return "{} - {}".format(element.SheetNumber, element.Name)
        if isinstance(element, DB.FamilySymbol):
            return "{} : {}".format(element.FamilyName, get_name(element))
        return get_name(element)


target = forms.CommandSwitchWindow.show([t[0] for t in TARGETS], message="Что переименовать?")
if not target:
    script.exit()
elements = dict(TARGETS)[target]()
if not elements:
    forms.alert("Нет элементов для переименования.", title="Переименование")
    script.exit()

pre_selected = set(revit.get_selection().element_ids)
items = sorted((NamedItem(e, checked=e.Id in pre_selected) for e in elements), key=lambda i: i.name)
selected = forms.SelectFromList.show(items, title="{}: отметьте элементы".format(target),
                                     multiselect=True, button_name="Далее")
if not selected:
    script.exit()

REPLACE, PREFIX, SUFFIX, UPPER, NUMBER = ("Найти и заменить", "Добавить префикс", "Добавить суффикс",
                                          "ВСЕ ЗАГЛАВНЫЕ", "Префикс + нумерация 01, 02...")
mode = forms.CommandSwitchWindow.show([REPLACE, PREFIX, SUFFIX, UPPER, NUMBER], message="Как переименовать?")
if not mode:
    script.exit()

if mode == REPLACE:
    find = forms.ask_for_string(prompt="Что найти:", title="Найти и заменить")
    if not find:
        script.exit()
    repl = forms.ask_for_string(prompt="На что заменить (можно оставить пустым):", title="Найти и заменить") or ""
    rule = lambda old, i: old.replace(find, repl)
elif mode in (PREFIX, NUMBER):
    prefix = forms.ask_for_string(prompt="Префикс:", title=mode)
    if prefix is None:
        script.exit()
    if mode == PREFIX:
        rule = lambda old, i: prefix + old
    else:
        rule = lambda old, i: "{}{:02d}".format(prefix, i + 1)
elif mode == SUFFIX:
    suffix = forms.ask_for_string(prompt="Суффикс:", title=mode)
    if suffix is None:
        script.exit()
    rule = lambda old, i: old + suffix
else:
    rule = lambda old, i: old.upper()

renamed, failed = [], []
with revit.Transaction("RevitTools: переименование ({})".format(target)):
    for index, element in enumerate(selected):
        old = get_name(element)
        new = rule(old, index)
        if new == old:
            continue
        try:
            element.Name = new
            renamed.append([old, new])
        except Exception as error:
            failed.append([old, new, str(error)])

output.print_md("# Переименовано: {}".format(len(renamed)))
if renamed:
    output.print_table(renamed, columns=["Было", "Стало"])
if failed:
    output.print_table(failed, columns=["Было", "Хотели", "Причина (часто — имя уже занято)"], title="Не удалось")

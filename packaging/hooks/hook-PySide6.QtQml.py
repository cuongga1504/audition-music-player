"""Ship only the Qt Quick modules used by this application.

The stock hook collects every installed QML plugin, including WebEngine/3D.
Filtering before dependency analysis keeps unused engines out of the bundle.
"""
from pathlib import PurePath
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()


def needed(entry):
    parts = PurePath(entry[1]).parts
    if 'qml' not in parts:
        return False
    module = parts[parts.index('qml') + 1:]
    if not module:
        return False
    if module[0] == 'QtQml':
        return True
    if module[0] != 'QtQuick':
        return False
    if len(module) == 1:
        return True
    if module[1] in ('Layouts', 'Window', 'Templates'):
        return True
    if module[1] == 'Controls':
        return len(module) == 2 or module[2] in ('Basic', 'impl')
    return False


binaries += [entry for entry in qml_binaries if needed(entry)]
datas += [entry for entry in qml_datas if needed(entry)]

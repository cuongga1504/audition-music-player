import QtQuick
import QtQuick.Controls
import "../theme"
Button {
    id: control
    property string iconName: ""
    property bool accent: false
    property bool active: false
    property string hint: text
    implicitWidth: 38
    implicitHeight: 32
    padding: 6
    hoverEnabled: true
    opacity: enabled ? 1 : 0.38
    Accessible.name: hint
    ToolTip.visible: hovered && hint.length > 0
    ToolTip.text: hint
    ToolTip.delay: 650
    background: Rectangle {
        radius: 7
        color: control.down ? Theme.border : (control.accent ? (control.hovered ? Theme.hover : Theme.primary) : (control.hovered ? Theme.surface : Theme.background))
        border.color: control.active || control.visualFocus ? Theme.primary : Theme.border
        border.width: control.active || control.visualFocus ? 2 : 1
        Rectangle { x: 2; y: parent.height - 4; width: parent.width - 4; height: 2; radius: 1; color: control.accent ? "#AE4711" : Theme.border; visible: !control.down }
    }
    contentItem: Item {
        implicitWidth: label.implicitWidth
        Image { anchors.centerIn: parent; width: 19; height: 19; source: control.iconName ? "../../assets/icons/" + control.iconName + (control.accent ? "-light" : (Theme.dark ? "-light" : "")) + ".svg" : ""; visible: control.iconName.length > 0 }
        Text { id: label; anchors.centerIn: parent; text: control.iconName ? "" : control.text; color: control.accent ? "#FFF5E1" : Theme.ink; font.family: Theme.font; font.pixelSize: 12; font.bold: control.active }
    }
}

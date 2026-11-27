pragma Singleton
import QtQuick
QtObject {
    readonly property bool dark: windowVM.darkTheme
    readonly property color background: dark ? "#252320" : "#F2E6D0"
    readonly property color surface: dark ? "#36322D" : "#E8D8BC"
    readonly property color primary: "#E86A17"
    readonly property color hover: "#FF812F"
    readonly property color ink: dark ? "#F2E6D0" : "#302C27"
    readonly property color muted: dark ? "#BCAE9A" : "#8B8072"
    readonly property color border: dark ? "#5D5347" : "#C9B99F"
    readonly property color charcoal: "#292724"
    readonly property string font: "Segoe UI"
}

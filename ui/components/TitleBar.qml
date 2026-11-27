import QtQuick
import QtQuick.Layouts
import "../theme"
Item {
    id: bar
    property bool back: false
    signal flipRequested()
    height: 62
    DragHandler { target: null; acceptedButtons: Qt.LeftButton; onActiveChanged: if (active) bar.Window.window.startSystemMove() }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 24; anchors.rightMargin: 18
        spacing: 8
        Image { source: "../../assets/icons/cassette.svg"; Layout.preferredWidth: 34; Layout.preferredHeight: 28 }
        ColumnLayout {
            spacing: 0
            Text { text: bar.back ? "Music Library" : "TBM Player"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 23; font.bold: true; font.italic: !bar.back }
            Text { text: bar.back ? libraryVM.count + " tracks · your offline collection" : "Game music. On tape."; color: Theme.muted; font.family: Theme.font; font.pixelSize: 10 }
        }
        Item { Layout.fillWidth: true }
        RetroButton { iconName: "flip"; hint: bar.back ? "Player · Tab" : "Music library · Tab"; onClicked: bar.flipRequested() }
        RetroButton { iconName: "pin"; hint: "Always on top"; active: windowVM.alwaysOnTop; implicitWidth: 28; onClicked: windowVM.togglePin() }
        RetroButton { iconName: "theme"; hint: "Light / dark theme"; implicitWidth: 28; onClicked: windowVM.toggleTheme() }
        RetroButton { iconName: "minimize"; hint: "Minimize · right click for tray"; implicitWidth: 28; onClicked: bar.Window.window.showMinimized(); TapHandler { acceptedButtons: Qt.RightButton; onTapped: windowVM.minimizeToTray() } }
        RetroButton { iconName: "close"; hint: "Close"; implicitWidth: 28; onClicked: bar.Window.window.close() }
    }
    Rectangle { anchors.bottom: parent.bottom; x: 24; width: parent.width - 48; height: 3; color: Theme.primary }
}

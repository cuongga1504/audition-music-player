import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
Rectangle {
    id: row
    required property int index
    required property string filePath
    required property string title
    required property string artist
    required property real duration
    required property bool favorite
    required property bool current
    signal contextRequested(string path, real x, real y)
    height: 43
    color: current ? Theme.primary : (mouse.containsMouse ? "#3A3630" : "transparent")
    radius: 5
    function clock(seconds) { if (!seconds) return "—"; let s = Math.floor(seconds); return Math.floor(s/60) + ":" + (s%60).toString().padStart(2, "0") }
    MouseArea {
        id: mouse; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
        onDoubleClicked: mouse => { if (mouse.button === Qt.LeftButton) libraryVM.play(row.filePath) }
        onClicked: mouse => { row.ListView.view.forceActiveFocus(); row.ListView.view.currentIndex = row.index; if (mouse.button === Qt.RightButton) row.contextRequested(row.filePath, mouse.x, mouse.y) }
    }
    RowLayout {
        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 8; spacing: 10
        Text { text: row.current && playerVM.playing ? "▶" : (row.index + 1).toString().padStart(2, "0"); color: row.current ? "#FFF1DA" : "#A99C89"; font.family: Theme.font; font.pixelSize: 12; Layout.preferredWidth: 24 }
        ColumnLayout { Layout.fillWidth: true; spacing: 0
            Text { text: row.title; color: "#F2E6D0"; font.family: Theme.font; font.pixelSize: 13; elide: Text.ElideRight; Layout.fillWidth: true }
            Text { visible: row.artist.length > 0; text: row.artist; color: row.current ? "#FFE2BB" : "#A99C89"; font.family: Theme.font; font.pixelSize: 9; elide: Text.ElideRight; Layout.fillWidth: true }
        }
        Text { text: row.clock(row.duration); color: "#E5D6BD"; font.family: Theme.font; font.pixelSize: 12 }
        Button {
            text: row.favorite ? "♥" : "♡"; implicitWidth: 28; implicitHeight: 30; hoverEnabled: true
            Accessible.name: row.favorite ? "Remove favorite" : "Add favorite"
            background: Rectangle { radius: 5; color: parent.hovered ? "#65503C" : "transparent" }
            contentItem: Text { text: parent.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: "#F2E6D0"; font.pixelSize: 19 }
            onClicked: libraryVM.favorite(row.filePath)
        }
    }
    Rectangle { x: 12; width: parent.width - 24; height: 1; anchors.bottom: parent.bottom; color: "#524B40"; visible: !row.current }
}

import QtQuick
import "../theme"
Rectangle {
    id: cassette
    property bool playing: false
    property real progress: 0
    property string title: ""
    radius: 19
    color: "#292724"
    border.color: "#9C8E78"; border.width: 3
    Rectangle { anchors.fill: parent; anchors.margins: 8; radius: 12; color: "#35332F"; border.color: "#565047" }
    Rectangle {
        id: label
        x: 37; y: 18; width: parent.width - 74; height: parent.height - 45
        radius: 9; color: "#F2E6D0"
        Rectangle { x: 0; y: 43; width: parent.width; height: parent.height - 43; color: "#E86A17"; radius: 6 }
        Text { x: 15; y: 7; width: parent.width - 30; height: 30; text: cassette.title; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: "#302C27"; font.family: "Segoe Print"; font.pixelSize: 20; font.italic: true; font.bold: true }
        Rectangle { x: 0; y: 40; width: parent.width; height: 1; color: "#C9B99F" }
        Rectangle { x: 12; y: 68; width: 35; height: 33; radius: 3; color: "#F2E6D0"; Text { anchors.centerIn: parent; text: "A"; color: "#C95512"; font.pixelSize: 25; font.bold: true } }
        Text { anchors.right: parent.right; anchors.rightMargin: 12; y: 70; text: "C-60"; font.pixelSize: 21; color: "#FFF0D7"; font.family: Theme.font }
        Rectangle {
            x: 60; y: 49; width: parent.width - 120; height: 77; radius: 38
            color: "#201F1C"; border.color: "#9A8060"; border.width: 2
            Rectangle { anchors.centerIn: parent; width: parent.width - 80; height: 23; radius: 3; color: "#504B3F"; border.color: "#7B6C56"
                Rectangle { x: 4; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 8; height: 4; color: "#806A46" }
            }
            TapeReel { x: 3; anchors.verticalCenter: parent.verticalCenter; width: 83; height: 83; spinning: cassette.playing; tapeAmount: 1 - cassette.progress }
            TapeReel { anchors.right: parent.right; anchors.rightMargin: 3; anchors.verticalCenter: parent.verticalCenter; width: 83; height: 83; spinning: cassette.playing; tapeAmount: cassette.progress }
        }
        Repeater { model: 2; Rectangle { required property int index; x: 0; y: label.height - 12 + index * 5; width: label.width; height: 2; color: "#F2E6D0" } }
    }
    Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 7; text: "SIDE A     •     STEREO     •     NORMAL POSITION"; font.pixelSize: 8; font.letterSpacing: 1.5; color: "#B6A78E" }
    Repeater { model: 4
        Rectangle { required property int index; x: index % 2 ? cassette.width - 21 : 13; y: index < 2 ? 13 : cassette.height - 21; width: 8; height: 8; radius: 4; color: "#252420"; border.color: "#6C6254"
            Rectangle { anchors.centerIn: parent; width: 4; height: 1; rotation: -30; color: "#998A73" }
        }
    }
}

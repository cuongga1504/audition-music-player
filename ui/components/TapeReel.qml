import QtQuick
Item {
    id: reel
    property bool spinning: false
    property real tapeAmount: 0.5
    Rectangle { anchors.centerIn: parent; width: parent.width * (0.70 + 0.29 * reel.tapeAmount); height: width; radius: width / 2; color: "#4B3D2B"; border.color: "#66543C"; border.width: 3 }
    Rectangle { anchors.centerIn: parent; width: parent.width * 0.68; height: width; radius: width / 2; color: "#DDD0B8"; border.width: 3; border.color: "#A99A82"
        Item {
            id: hub
            objectName: "reelHub"
            anchors.fill: parent
            RotationAnimation on rotation { id: spin; from: 0; to: 360; duration: 2600; loops: Animation.Infinite; running: true; paused: !reel.spinning }
            Rectangle { anchors.centerIn: parent; width: parent.width * 0.66; height: width; radius: width / 2; color: "#292724" }
            Repeater { model: 6
                Item { required property int index; anchors.fill: parent; rotation: index * 60
                    Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: 7; width: 8; height: 12; radius: 1; color: "#DDD0B8" }
                }
            }
            Rectangle { anchors.centerIn: parent; width: 15; height: 15; radius: 8; color: "#45403A"; border.color: "#777065" }
        }
    }
}

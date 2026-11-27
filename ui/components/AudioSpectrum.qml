import QtQuick
import "../theme"
Item {
    id: spectrum
    property var levels: playerVM.spectrum
    Row {
        anchors.fill: parent; spacing: 3
        Repeater { model: 24
            Item { required property int index; width: (spectrum.width - 69) / 24; height: spectrum.height
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Math.max(2, spectrum.levels[index] * parent.height); color: Theme.primary; opacity: spectrum.levels[index] > 0 ? 1 : 0.2 }
            }
        }
    }
}

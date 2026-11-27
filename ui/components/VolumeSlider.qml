import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
RowLayout {
    spacing: 9
    RetroButton { iconName: playerVM.muted ? "mute" : "volume"; hint: "Mute"; implicitWidth: 30; implicitHeight: 26; active: playerVM.muted; onClicked: playerVM.toggleMute() }
    Slider {
        id: volume
        Layout.fillWidth: true
        from: 0; to: 1; value: playerVM.volume
        onMoved: playerVM.setVolume(value)
        Accessible.name: "Volume"
        background: Rectangle { x: volume.leftPadding; y: volume.topPadding + volume.availableHeight / 2 - 3; width: volume.availableWidth; height: 6; radius: 3; color: Theme.border
            Rectangle { width: volume.visualPosition * parent.width; height: parent.height; radius: 3; color: Theme.primary; opacity: playerVM.muted ? 0.3 : 1 }
        }
        handle: Rectangle { x: volume.leftPadding + volume.visualPosition * (volume.availableWidth - width); y: volume.topPadding + volume.availableHeight / 2 - height / 2; width: 14; height: 14; radius: 7; color: Theme.background; border.color: volume.visualFocus ? Theme.primary : Theme.muted }
    }
}

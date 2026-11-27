import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
RowLayout {
    function clock(ms) { let s = Math.max(0, Math.floor(ms / 1000)); return Math.floor(s / 60).toString().padStart(2, "0") + ":" + (s % 60).toString().padStart(2, "0") }
    spacing: 14
    Text { text: clock(seek.pressed ? seek.value : playerVM.position); color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.preferredWidth: 45 }
    Slider {
        id: seek
        Layout.fillWidth: true
        from: 0; to: Math.max(1, playerVM.duration)
        enabled: playerVM.hasTrack && !playerVM.busy
        Binding { target: seek; property: "value"; value: playerVM.position; when: !seek.pressed; restoreMode: Binding.RestoreNone }
        onPressedChanged: if (!pressed) playerVM.seek(Math.round(value))
        onMoved: if (!pressed) playerVM.seek(Math.round(value))
        Accessible.name: "Playback position"
        background: Rectangle { x: seek.leftPadding; y: seek.topPadding + seek.availableHeight / 2 - 3; width: seek.availableWidth; height: 6; radius: 3; color: Theme.border
            Rectangle { width: seek.visualPosition * parent.width; height: parent.height; radius: 3; color: Theme.primary }
        }
        handle: Rectangle { x: seek.leftPadding + seek.visualPosition * (seek.availableWidth - width); y: seek.topPadding + seek.availableHeight / 2 - height / 2; width: 16; height: 16; radius: 8; color: Theme.background; border.color: seek.visualFocus ? Theme.primary : Theme.muted; border.width: 2 }
    }
    Text { text: clock(playerVM.duration); color: Theme.ink; font.family: Theme.font; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.preferredWidth: 45; horizontalAlignment: Text.AlignRight }
}

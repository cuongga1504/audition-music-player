import QtQuick
import QtQuick.Layouts
RowLayout {
    property bool mini: false
    spacing: mini ? 6 : 12
    RetroButton {
        objectName: mini ? "libraryShuffleButton" : "playerShuffleButton"
        iconName: "shuffle"
        hint: playerVM.shuffle ? "Shuffle: on" : "Shuffle: off"
        active: playerVM.shuffle
        accent: playerVM.shuffle
        Accessible.checkable: true
        Accessible.checked: playerVM.shuffle
        Layout.preferredWidth: mini ? 30 : 68
        Layout.preferredHeight: mini ? 30 : 44
        onClicked: playerVM.toggleShuffle()
    }
    RetroButton { iconName: "previous"; hint: "Previous · Ctrl+Left"; enabled: libraryVM.count > 0; Layout.preferredWidth: mini ? 34 : 76; Layout.preferredHeight: mini ? 30 : 44; onClicked: playerVM.previous() }
    RetroButton { iconName: playerVM.playing ? "pause" : "play"; hint: playerVM.playing ? "Pause · Space" : "Play · Space"; accent: true; enabled: !playerVM.busy && libraryVM.count > 0; Layout.preferredWidth: mini ? 42 : 94; Layout.preferredHeight: mini ? 30 : 48; onClicked: playerVM.toggle() }
    RetroButton { iconName: "next"; hint: "Next · Ctrl+Right"; enabled: libraryVM.count > 0; Layout.preferredWidth: mini ? 34 : 76; Layout.preferredHeight: mini ? 30 : 44; onClicked: playerVM.next() }
    RetroButton { visible: !mini; iconName: playerVM.repeat === 1 ? "repeat-one" : "repeat"; hint: ["Repeat off", "Repeat track", "Repeat all"][playerVM.repeat]; active: playerVM.repeat > 0; Layout.preferredWidth: 68; Layout.preferredHeight: 44; onClicked: playerVM.cycleRepeat() }
}

import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"
Item {
    id: page
    property bool active: true
    signal flipRequested()
    TitleBar { id: header; width: parent.width; onFlipRequested: page.flipRequested() }
    Cassette { x: 48; y: 78; width: parent.width - 96; height: 195; title: playerVM.hasTrack ? playerVM.title : "Drop a TBM. Press play."; playing: playerVM.playing && page.active; progress: playerVM.duration > 0 ? playerVM.position / playerVM.duration : 0 }
    ProgressSlider { x: 48; y: 282; width: parent.width - 96; height: 31 }
    PlayerControls { anchors.horizontalCenter: parent.horizontalCenter; y: 326; height: 48 }
    VolumeSlider { x: 48; y: 386; width: 232; height: 28 }
    AudioSpectrum { x: 365; y: 386; width: 225; height: 26; visible: page.active }
    Text { x: 48; y: 419; width: parent.width - 96; text: libraryVM.status; elide: Text.ElideRight; color: playerVM.busy ? Theme.primary : Theme.muted; font.family: Theme.font; font.pixelSize: 9 }
}

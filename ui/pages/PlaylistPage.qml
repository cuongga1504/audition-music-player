import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"
Item {
    id: page
    signal flipRequested()
    TitleBar { width: parent.width; back: true; onFlipRequested: page.flipRequested() }
    RowLayout {
        x: 24; y: 75; width: parent.width - 48; height: 33; spacing: 6
        TextField { id: search; objectName: "searchInput"; placeholderText: "Search your music…"; placeholderTextColor: Theme.muted; Layout.fillWidth: true; Layout.preferredHeight: 32; color: Theme.ink; font.family: Theme.font; font.pixelSize: 12; selectByMouse: true; onTextChanged: libraryVM.search(text); background: Rectangle { color: Theme.surface; radius: 6; border.color: search.activeFocus ? Theme.primary : Theme.border } }
        RetroButton { iconName: "file"; hint: "Open files · Ctrl+O"; onClicked: libraryVM.openFiles() }
        RetroButton { iconName: "folder"; hint: "Open folder · Ctrl+Shift+O"; onClicked: libraryVM.openFolder() }
        RetroButton { iconName: "refresh"; hint: "Refresh library"; onClicked: libraryVM.refresh() }
        RetroButton { iconName: "heart"; hint: "Favorites"; active: libraryVM.favoritesOnly; onClicked: libraryVM.toggleFavorites() }
        RetroButton { iconName: "sort"; hint: "Sort tracks"; onClicked: sortMenu.popup()
            Menu {
                id: sortMenu
                MenuItem { text: "Title A–Z"; onTriggered: libraryVM.sort(0) }
                MenuItem { text: "Title Z–A"; onTriggered: libraryVM.sort(1) }
                MenuItem { text: "Duration"; onTriggered: libraryVM.sort(2) }
            }
        }
    }
    Rectangle {
        x: 24; y: 120; width: parent.width - 48; height: 235; radius: 12; color: Theme.charcoal
        ListView {
            id: list
            objectName: "trackList"
            anchors.fill: parent; anchors.margins: 9
            clip: true; model: playlistModel; spacing: 2; reuseItems: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { }
            keyNavigationEnabled: true
            Keys.onReturnPressed: if (currentItem) libraryVM.play(currentItem.filePath)
            delegate: TrackListItem {
                width: ListView.view.width
                border.width: ListView.isCurrentItem && list.activeFocus ? 1 : 0
                border.color: "#E8D8BC"
                onContextRequested: (path, x, y) => { context.trackPath = path; context.popup(this, x, y) }
            }
        }
        Column {
            anchors.centerIn: parent; spacing: 12; visible: libraryVM.visibleCount === 0
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: libraryVM.count ? "No matching tracks" : "Your collection starts here"; color: "#F2E6D0"; font.family: Theme.font; font.pixelSize: 18; font.bold: true }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "Open a folder or drop your TBM files into the player."; color: "#B5A58E"; font.family: Theme.font; font.pixelSize: 11 }
            RetroButton { anchors.horizontalCenter: parent.horizontalCenter; text: "Open music folder"; implicitWidth: 150; accent: true; visible: libraryVM.count === 0; onClicked: libraryVM.openFolder() }
        }
    }
    Menu {
        id: context
        property string trackPath: ""
        MenuItem { text: "Play"; onTriggered: libraryVM.play(context.trackPath) }
        MenuItem { text: "Play next"; onTriggered: libraryVM.playNext(context.trackPath) }
        MenuItem { text: "Toggle favorite"; onTriggered: libraryVM.favorite(context.trackPath) }
        MenuItem { text: "Open file location"; onTriggered: libraryVM.reveal(context.trackPath) }
        MenuItem { text: "Export decoded OGG…"; onTriggered: libraryVM.export(context.trackPath) }
        MenuSeparator { }
        MenuItem { text: "Remove from playlist"; onTriggered: libraryVM.remove(context.trackPath) }
    }
    RowLayout {
        x: 26; y: 369; width: parent.width - 52; height: 40; spacing: 12
        Image { source: "../../assets/icons/cassette.svg"; Layout.preferredWidth: 28; Layout.preferredHeight: 24 }
        ColumnLayout { Layout.fillWidth: true; spacing: 1
            Text { text: playerVM.hasTrack ? playerVM.title : "No tape loaded"; color: Theme.ink; font.family: Theme.font; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
            Text { text: playerVM.busy ? "Decoding…" : (playerVM.playing ? "Now playing · Side A" : "Ready when you are"); color: Theme.muted; font.family: Theme.font; font.pixelSize: 10 }
        }
        PlayerControls { mini: true }
    }
    Text { x: 26; y: 420; width: parent.width - 52; text: libraryVM.status; color: Theme.muted; elide: Text.ElideRight; font.family: Theme.font; font.pixelSize: 9 }
}

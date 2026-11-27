import QtQuick
import QtQuick.Controls
import "components"
import "pages"
import "theme"
ApplicationWindow {
    id: window
    objectName: "mainWindow"
    width: 640; height: 440
    minimumWidth: 640; maximumWidth: 640
    minimumHeight: 440; maximumHeight: 440
    visible: true
    title: "TBM Cassette Player"
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"
    font.family: Theme.font
    function editing() { let item = activeFocusItem; return item && (item.hasOwnProperty("echoMode") || item.hasOwnProperty("inputMethodHints")) }
    function flip() { if (!card.moving) { card.flipped = !card.flipped; window.contentItem.forceActiveFocus() } }
    FlipCard {
        id: card; objectName: "flipCard"; anchors.fill: parent
        front: Rectangle { anchors.fill: parent; radius: 16; color: Theme.background; border.color: Theme.border; enabled: !card.flipped && !card.moving
            PlayerPage { anchors.fill: parent; active: !card.flipped && !card.moving; onFlipRequested: window.flip() }
        }
        back: Rectangle { anchors.fill: parent; radius: 16; color: Theme.background; border.color: Theme.border; enabled: card.flipped && !card.moving
            PlaylistPage { anchors.fill: parent; onFlipRequested: window.flip() }
        }
    }
    DropArea { anchors.fill: parent; onDropped: drop => { if (drop.hasUrls) { libraryVM.dropFiles(drop.urls); drop.acceptProposedAction() } } }
    Shortcut { sequence: "Space"; enabled: !window.editing(); onActivated: playerVM.toggle() }
    Shortcut { sequence: "Ctrl+Right"; onActivated: playerVM.next() }
    Shortcut { sequence: "Ctrl+Left"; onActivated: playerVM.previous() }
    Shortcut { sequence: "Ctrl+O"; onActivated: libraryVM.openFiles() }
    Shortcut { sequence: "Ctrl+Shift+O"; onActivated: libraryVM.openFolder() }
    Shortcut { sequence: "Tab"; enabled: !window.editing(); onActivated: window.flip() }
    Shortcut { sequence: "Up"; enabled: !window.editing() && !card.flipped; onActivated: playerVM.setVolume(playerVM.volume + 0.05) }
    Shortcut { sequence: "Down"; enabled: !window.editing() && !card.flipped; onActivated: playerVM.setVolume(playerVM.volume - 0.05) }
}

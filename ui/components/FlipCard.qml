import QtQuick
Flipable {
    id: card
    property bool flipped: false
    readonly property bool moving: motion.running
    transform: Rotation { id: turn; origin.x: card.width / 2; origin.y: card.height / 2; axis.x: 0; axis.y: 1; axis.z: 0; angle: card.flipped ? 180 : 0
        Behavior on angle { NumberAnimation { id: motion; duration: 400; easing.type: Easing.InOutCubic } }
    }
    onFlippedChanged: playerVM.setFrontVisible(!flipped)
}

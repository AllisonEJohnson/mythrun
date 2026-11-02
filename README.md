# Mythrun

A dark-fantasy 3D obstacle course game for the browser, built with three.js.

**Play:** https://allisonejohnson.github.io/mythrun/

The whole game is the single file `index.html`. Progress, unlocks, and your custom Course 2 layout are saved in your browser's localStorage, so they stay on the device you play on.

## Art

The dungeon scenery comes from the licensed ithappy Dungeon pack, which lives in the private `madison-game-art` repository. Only the pieces the game uses are baked into `index.html` as compact mesh data (the `dungeon-art` script block); no pack files are stored here. Those baked pieces are part of this game and are not licensed for reuse elsewhere.

To change which pieces are baked, edit `PIECES` in `tools/pack_dungeon_art.py` and run it against a checkout of the art repository:

```
python3 tools/pack_dungeon_art.py --art ../madison-game-art/Dungeon
```

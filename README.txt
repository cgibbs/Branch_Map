This is an undergrad research project based around Steganography in 2D game maps. The functionality is pretty basic right now, as it isn't much more than a proof of concept, but the basic gist of the idea is that it encodes a message within the shape of the map, using in-game items within each room as "bits" to represent each character.

Most of this code is based on two of my previous projects, PyWizardry and (more importantly) PyRoguelike, which are available on my Github, as well. (github.com/cgibbs, in case you found this somewhere else.) The maps generated in this program should be more or less compatible with PyRoguelike.

Currently hard-coded to generate a map hiding the following message:

"Nine-tenths of tactics are certain, and taught in books: but the irrational tenth is like the kingfisher flashing across the pool, and that is the test of generals."
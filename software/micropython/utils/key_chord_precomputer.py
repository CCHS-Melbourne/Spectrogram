#straight out of sonnet 4.6
import json

modes = {
    'Ionian':     [1,0,1,0,1,1,0,1,0,1,0,1],
    'Dorian':     [1,0,1,1,0,1,0,1,0,1,1,0],
    'Phrygian':   [1,1,0,1,0,1,0,1,1,0,1,0],
    'Lydian':     [1,0,1,0,1,0,1,1,0,1,0,1],
    'Mixolydian': [1,0,1,0,1,1,0,1,0,1,1,0],
    'Aeolian':    [1,0,1,1,0,1,0,1,1,0,1,0],
    'Locrian':    [1,1,0,1,0,1,1,0,1,0,1,0],
}

notes = ['c','c#','d','d#','e','f','f#','g','g#','a','a#','b']

chord_to_keys = {}

for mode_name, mask in modes.items():
    for root in range(12):
        scale = [(root + i) % 12 for i in range(12) if mask[i] == 1]
        
        triad = frozenset([scale[0], scale[2], scale[4]])
        seventh = frozenset([scale[0], scale[2], scale[4], scale[6]])
        
        key_name = f"{notes[root]}_{mode_name}"
        
        for chord in [triad, seventh]:
            if chord not in chord_to_keys:
                chord_to_keys[chord] = []
            if key_name not in chord_to_keys[chord]:
                chord_to_keys[chord].append(key_name)

# serialise — frozensets need converting for JSON
out = {}
for k, v in chord_to_keys.items():
    out[','.join(str(n) for n in sorted(k))] = v

with open('chord_lut.json', 'w') as f:
    json.dump(out, f)

print("done, entries:", len(out))
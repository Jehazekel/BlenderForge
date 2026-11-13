# Village scene

Everything below is built into one .blend. Lines starting with `//` are comments.

# settings
fps: 24  seed: 4  render: village.png  resolution: 1600x900  export: glb

# map: Valley
type: valley  size: 90  height: 22  trees: 45  rocks: 18  houses: 2

# structure: Watchtower
type: castle_tower  floors: 3  radius: 2.2  roof: cone  windows: 6
position: -10, -24

# structure: Inn
type: house  width: 9  depth: 6  floors: 2  material: plaster  roof_color: #7b3327
position: 2, -27  rotation: 10

# character: Knight
type: knight  height: 1.8  skin: #c68642  accessories: helmet, sword, shield
animation: idle, walk, wave  expression: smile
position: -4, -30

# character: Wizard
type: wizard  height: 1.75  skin: #e0b08a  hair: long  hair_color: #d8d8d8
animation: idle, wave
position: -2, -30  rotation: -20

# animal: Wolf
type: wolf  size: 1.2  fur: #555555
animation: sit, tail_sway
position: -5.5, -29  rotation: 30

# animal: Hawk
type: eagle  size: 0.7
animation: fly
position: -6, -26, 16

# vehicle: Cart
type: cart
position: 5.5, -31  rotation: 70

# prop: Well
type: well
position: 0.5, -32

# prop: Campfire
type: campfire
position: -3.5, -32.5

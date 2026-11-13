"""One module per template. A template module defines:

    NAMES = ["tower", "castle_tower"]      # values accepted by `type:`
    def build(spec, ctx, type_name): ...   # returns forge.core.Entity

Drop a new file in this folder and it is picked up automatically.
"""

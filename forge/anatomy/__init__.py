"""Anatomy system, in four layers kept apart on purpose:

1. profiles.py + data/*.json   the anatomical profile database (pure data)
2. skeleton.py                 landmark and constraint solver (pure maths)
3. templates/tetrapod.py ...   procedural geometry that only reads landmarks
4. creature.py, scene.py       Blender integration and export

validate.py checks a solved skeleton and the finished mesh; reference.py
measures silhouettes in reference images and fits a profile to them.
Layers 1, 2 and the checks never import bpy, so a new species is new data,
not new modelling code.
"""

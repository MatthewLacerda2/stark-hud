"""Getting a mesh onto the board: turning 3D files into the OBJ the widget reads.

Two halves, and they run in different places. ``convert`` runs on this machine
and drives Blender; ``samples`` runs *inside* Blender and builds the objects the
widget was written against. Neither is imported by the agent — these are things
a person runs, not a loop that feeds panels.
"""

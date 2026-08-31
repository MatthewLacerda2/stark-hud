"""Business logic layer.

Logic that is neither a thin handler nor plain state access lives here.
``placement`` decides where an item may sit on the grid; ``board`` composes that
with the repository so handlers stay thin.
"""

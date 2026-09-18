"""Application/service layer (milestone M4).

Sits between the API and the store: routes translate HTTP, services express use
cases, the store persists. No SQL in route handlers (docs/06 §3, AD-03), and no
merge logic here — folds stay in ``rescuenet.projections``.
"""

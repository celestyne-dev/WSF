# Marshmallow schemas for request validation and response serialization,
# one module per model in app/models/. All read schemas set
# `load_instance = False` — writes go through explicit input schemas
# (RegisterSchema, LoginSchema, ...) rather than deserializing straight
# into ORM instances, keeping validation and persistence separate.

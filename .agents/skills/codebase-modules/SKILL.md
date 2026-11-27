---
name: codebase-modules
description: >-
  Place backend code in the module scaffold (models, api, schemas, errors,
  utils) and update MODULE.md or SERVICE.md in the same change. Use when
  adding or editing a module, service folder, route, model, schema, or docs
  named MODULE.md or SERVICE.md in tab-intranet-be or tab-be.
---

# Modules

A module is a domain package at the backend root. It is not a module if the scaffold is missing, even when a folder has no files yet.

## Required scaffold

Every module has these folders, with `__init__.py` even when empty:

```
<module>/
  MODULE.md
  api/v1/
  models/
  schemas/
  errors/
  utils/
```

New files go in one of these folders. The module root keeps only `MODULE.md`, `__init__.py`, and package data (fonts, logos, static files that belong to the module).

## Where code goes

| Folder | Put here | Keep out |
|---|---|---|
| `models/` | SQLAlchemy table or persisted domain shape. A method on the model only when it uses fields already loaded on the instance. | Queries on other tables, permissions, HTTP. |
| `schemas/` | Pydantic request and response contracts. | Logic and database access. |
| `api/v1/` | Thin FastAPI routes: validate, call `utils` or another module, map errors. | Long business rules. |
| `errors/` | Domain exceptions and `http_error_*` functions. | Happy paths. |
| `utils/` | Checks, stores, dependencies, parsing, rendering. | Table definitions. |

A `hybrid_property` belongs on the model only when the same calculation must work in Python and inside a SQL query. A check that reads other tables belongs in `utils`.

Import a module through its public surface (`from documents import export_document`). Routes do not reach into another module's internal files past that surface.

## Services

A service folder lends a capability that modules use. It has `SERVICE.md`, not `MODULE.md`.

`api`, `models`, `schemas`, and `errors` are not services: document them in the module's `MODULE.md`. A module's `utils` folder is part of the scaffold; if that folder has a `SERVICE.md`, update it as a service.

## Docs in the same change

A change to behavior, responsibilities, or who talks to whom updates the doc before the work is done.

- Module: `MODULE.md` at the module root.
- Service: `SERVICE.md` in the service folder.

Sections, in English, only the ones that changed:

```markdown
# Name

## Purpose
## What it owns
## Who it talks to
```

An internal change that leaves those three untouched leaves the file as it is. A new module or service folder is created with the file already in place.

---
name: codebase-logic
description: >-
  Write backend code so each piece of logic lives in one place: entity
  methods on models, contracts in schemas, API errors in errors, support
  functions in utils, and route handlers only in api. Use when adding or
  editing models, routes, schemas, errors, or utils in tab-intranet-be or
  tab-be.
---

# Module logic

Each behavior lives in one place. Do not copy a condition or a function into a second file.

## models

The model, its properties, and methods bound to the entity already loaded.

A method reads or updates fields on that row: `is_file`, `needs_classification`, `reject`. It does not open a query, call another model, or build an HTTP response.

## schemas

Every contract: requests, responses, and the types that enter or leave the API. No queries and no business rules.

## errors

Every API error: domain exceptions and `http_error_*` functions. Happy paths do not go through here.

## utils

The module's internal library. Everything that supports the module and is not the entity itself: queries, use cases, parsing, stores, dependencies.

A utils function receives the model or the session and does the work. If two routes do the same thing, there is one function, in utils.

## api

The route file contains only handlers. No extra functions, no private helpers that hold logic.

A handler does this, and nothing more:

1. Read the contract.
2. Load the entity by calling utils.
3. Check the permission.
4. Call a model method or a utils function.
5. Commit when the session changed.
6. Return the contract.

If the handler goes past this list, move the logic into utils or onto the model.

# Backend Architecture: Layered Architecture, Modular Monolith, and Clean Architecture

## Scope

Backend architecture determines how responsibilities, dependencies, business rules, infrastructure, and deployment boundaries are arranged inside a software system.

This repository treats three related architectural approaches as distinct mechanisms:

| Architecture | Primary concern | Boundary being emphasized |
|---|---|---|
| Layered architecture | Separation of technical responsibilities | API, application, domain, infrastructure layers |
| Modular monolith | Separation of business capabilities within one deployment | Explicit business modules and their public interfaces |
| Clean architecture | Direction of dependencies around business policy | Inner domain/application policy isolated from external mechanisms |

These approaches are not mutually exclusive. A modular monolith can use layers inside each module, while clean-architecture dependency rules can govern the direction of dependencies inside those layers.

The central distinction is architectural intent. Layering organizes technical responsibilities. Modularization organizes business capabilities. Clean architecture controls dependency direction so that business policy is not owned by external frameworks or infrastructure.

## Core Architectural Relationships

A useful backend can be represented as a combination of boundaries rather than as a choice between three unrelated patterns.

```text
                    HTTP / API / Messaging
                             |
                             v
                    Application Services
                             |
                             v
                       Domain Policy
                             ^
                             |
                  Ports / Interfaces
                             ^
                             |
                   Infrastructure Adapters

# Couverture de la documentation FastAPI

> Ce cursus **couvre l'intégralité** de la documentation officielle FastAPI (Tutorial,
> Advanced User Guide, How-To) plus les deux pré-requis « Learn » (types Python, async).
> Ce tableau relie **chaque page** de la doc au(x) module(s) où elle est enseignée,
> pratiquée et intégrée dans `taskman`.
>
> Coche une page quand tu l'as : (1) lue dans la doc officielle, (2) travaillée via
> l'exercice du module, (3) retrouvée dans le code de `taskman`.

Référence : <https://fastapi.tiangolo.com/learn/>

---

## Learn — pré-requis

| Page doc | Module | Statut |
|---|---|---|
| Python Types Intro | 01 (§ rappel) + [`annexes/python-typing.md`](annexes/python-typing.md) | ☐ |
| Concurrency and `async` / `await` | 01 (théorie ASGI) + 08 (approfondi) | ☐ |

## Tutorial - User Guide

| Page doc | Module | Statut |
|---|---|---|
| First Steps | 01 | ☐ |
| Path Parameters | 01 | ☐ |
| Query Parameters | 01 | ☐ |
| Request Body | 01 | ☐ |
| Query Parameters and String Validations | 01 | ☐ |
| Path Parameters and Numeric Validations | 01 | ☐ |
| Query Parameter Models | 02 | ☐ |
| Body - Multiple Parameters | 02 | ☐ |
| Body - Fields | 02 | ☐ |
| Body - Nested Models | 02 | ☐ |
| Declare Request Example Data | 02 | ☐ |
| Extra Data Types | 02 | ☐ |
| Cookie Parameters | 02 | ☐ |
| Header Parameters | 02 | ☐ |
| Cookie Parameter Models | 02 | ☐ |
| Header Parameter Models | 02 | ☐ |
| Response Model - Return Type | 02 | ☐ |
| Extra Models | 02 | ☐ |
| Response Status Code | 01 / 02 | ☐ |
| Form Data | 02 (annexe) | ☐ |
| Form Models | 02 (annexe) | ☐ |
| Request Files | 02 (annexe) + 08 (upload) | ☐ |
| Request Forms and Files | 02 (annexe) | ☐ |
| Handling Errors | 05 | ☐ |
| Path Operation Configuration | 03 | ☐ |
| JSON Compatible Encoder (`jsonable_encoder`) | 04 | ☐ |
| Body - Updates (`PUT` / `PATCH`) | 02 | ☐ |
| Dependencies | 03 | ☐ |
| — Classes as Dependencies | 03 | ☐ |
| — Sub-dependencies | 03 | ☐ |
| — Dependencies in path operation decorators | 03 | ☐ |
| — Global Dependencies | 03 | ☐ |
| — Dependencies with `yield` | 03 / 04 | ☐ |
| Security | 06 | ☐ |
| — Security - First Steps | 06 | ☐ |
| — Get Current User | 06 | ☐ |
| — Simple OAuth2 with Password and Bearer | 06 | ☐ |
| — OAuth2 with Password (hashing), Bearer with JWT | 06 | ☐ |
| Middleware | 05 | ☐ |
| CORS (Cross-Origin Resource Sharing) | 05 / 10 | ☐ |
| SQL (Relational) Databases | 04 | ☐ |
| Bigger Applications - Multiple Files | 03 | ☐ |
| Stream JSON Lines | 08 | ☐ |
| Server-Sent Events (SSE) | 08 / 12 | ☐ |
| Background Tasks | 08 | ☐ |
| Metadata and Docs URLs | 03 / 09 | ☐ |
| Static Files | 09 (annexe) | ☐ |
| Testing | 07 | ☐ |
| Debugging | 07 (annexe) | ☐ |

## Advanced User Guide

| Page doc | Module | Statut |
|---|---|---|
| Path Operation Advanced Configuration | 03 / 12 | ☐ |
| Additional Status Codes | 05 | ☐ |
| Return a Response Directly | 05 | ☐ |
| Custom Response - HTML, Stream, File, others | 08 | ☐ |
| Additional Responses in OpenAPI | 05 | ☐ |
| Response Cookies | 06 | ☐ |
| Response Headers | 05 | ☐ |
| Response - Change Status Code | 05 | ☐ |
| Advanced Dependencies | 03 | ☐ |
| Advanced Security — OAuth2 scopes | 06 | ☐ |
| Advanced Security — HTTP Basic Auth | 06 (annexe) | ☐ |
| Using the Request Directly | 05 | ☐ |
| Using Dataclasses | 02 (annexe) | ☐ |
| Advanced Middleware | 05 / 10 | ☐ |
| Sub Applications - Mounts | 12 | ☐ |
| Behind a Proxy | 11 | ☐ |
| Templates | 09 (annexe) | ☐ |
| WebSockets | 12 | ☐ |
| Lifespan Events | 03 / 04 | ☐ |
| Testing WebSockets | 12 | ☐ |
| Testing Events: lifespan and startup/shutdown | 07 | ☐ |
| Testing Dependencies with Overrides | 07 | ☐ |
| Async Tests | 07 | ☐ |
| Settings and Environment Variables | 03 | ☐ |
| OpenAPI Callbacks | 12 (annexe) | ☐ |
| OpenAPI Webhooks | 12 | ☐ |
| Including WSGI - Flask, Django, others | 12 (annexe) | ☐ |
| Generating SDKs | 11 (annexe) | ☐ |
| Advanced Python Types | 02 | ☐ |
| JSON with Bytes as Base64 | 02 (annexe) | ☐ |
| Strict Content-Type Checking | 10 | ☐ |

## Deployment

| Page doc | Module | Statut |
|---|---|---|
| About FastAPI versions | 11 | ☐ |
| About HTTPS | 11 | ☐ |
| Run a Server Manually (Uvicorn) | 11 | ☐ |
| Deployments Concepts | 11 | ☐ |
| Deploy FastAPI on Cloud Providers | 11 (annexe) | ☐ |
| Server Workers - Uvicorn with Workers | 11 | ☐ |
| FastAPI in Containers - Docker | 11 | ☐ |

## How To - Recipes

| Page doc | Module | Statut |
|---|---|---|
| Migrate from Pydantic v1 to Pydantic v2 | 02 (annexe) | ☐ |
| GraphQL | 12 (annexe, hors scope principal) | ☐ |
| Custom Request and APIRoute class | 05 (annexe) | ☐ |
| Conditional OpenAPI | 09 / 10 | ☐ |
| Extending OpenAPI | 12 (annexe) | ☐ |
| Separate OpenAPI Schemas for Input and Output or Not | 02 | ☐ |
| Custom Docs UI Static Assets (Self-Hosting) | 09 (annexe) | ☐ |
| Configure Swagger UI | 09 (annexe) | ☐ |
| Testing a Database | 07 | ☐ |
| Use Old 403 Authentication Error Status Codes | 06 (annexe) | ☐ |

## FastAPI CLI & outillage

| Page doc | Module | Statut |
|---|---|---|
| FastAPI CLI (`fastapi dev` / `fastapi run`) | 00 / 01 | ☐ |
| Editor Support | 00 | ☐ |
| AI Agent Skills (skill officiel FastAPI) | 00 (annexe) | ☐ |

---

## Reference (API technique)

La *Reference* documente les classes/fonctions une par une. On la travaille **au fil des
modules**, comme dictionnaire — pas linéairement.

| Page Reference | Module principal |
|---|---|
| `FastAPI` class | 01 / 03 |
| Request Parameters (`Path`, `Query`, `Body`, `Form`, `Cookie`, `Header`, `File`) | 01 / 02 |
| Status Codes | 01 |
| `UploadFile` class | 08 |
| Exceptions — `HTTPException`, `WebSocketException` | 05 |
| Dependencies — `Depends()`, `Security()` | 03 / 06 |
| `APIRouter` class | 03 |
| `BackgroundTasks` | 08 |
| `Request` class | 05 |
| `WebSockets` | 12 |
| `HTTPConnection` class | 12 |
| `Response` class | 05 |
| Custom Response Classes (`FileResponse`, `HTMLResponse`, `RedirectResponse`, `StreamingResponse`…) | 05 / 08 |
| Server-Sent Events (`EventSourceResponse`, `ServerSentEvent`) | 08 / 12 |
| `Middleware` | 05 |
| `OpenAPI` / OpenAPI docs / OpenAPI models | 09 / 12 |
| Security Tools | 06 |
| `jsonable_encoder` | 04 |
| `StaticFiles` | 09 |
| `Jinja2Templates` | 09 |
| `TestClient` | 07 |

## Features & écosystème (lecture)

- **Features** (page « FastAPI features ») : lue en intro du Module 01 — comprendre *ce que*
  le framework promet (OpenAPI, docs auto, typage, validation Pydantic, DI, base Starlette).
- **Full Stack FastAPI Template**, FastAPI People, Help, Contributing, Translations,
  External Links, newsletter : ressources communautaires, parcourues en fin de cursus.

## Petits projets (checkpoints)

Des mini-projets **hors `taskman`** pour valider un bloc de compétences sur un domaine neuf :

| Après le module | Projet | Ce qu'il valide |
|---|---|---|
| 02 | **`linkstash`** — API de marque-pages (URL, tags, notes) | routing, Pydantic, validation, response models |
| 04 | **`shorturl`** — raccourcisseur d'URL avec compteur de clics | DB, migrations, repository, contraintes d'unicité |
| 07 | **`pollup`** — API de sondages (questions, options, votes) | archi en couches + suite de tests complète en TDD |
| 09 | **`statuspage`** — API de supervision de services | observabilité, health/ready, métriques, tâches de fond |
| 12 | **`taskman` v2** refait de zéro en 2 jours | maîtrise réelle, sans filet |

Chaque mini-projet a son énoncé dans [`projets/`](projets/) et une solution de référence.

# Module 02 — Modélisation & validation des données

> 🚧 **Module en construction.** Sa structure finale : `THEORIE.md` · `PAS-A-PAS.md` ·
> `exercices/` · `solutions/`. On le construit ensemble après validation du Module 01.

## Objectif

Concevoir des **contrats d'API explicites, impossibles à mal utiliser** : ce qui entre, ce
qui est stocké et ce qui sort sont trois choses distinctes.

## Pages de doc FastAPI couvertes

Query Parameter Models · Body - Multiple Parameters · Body - Fields · Body - Nested Models ·
Declare Request Example Data · Extra Data Types · Cookie/Header Parameters (+ Models) ·
Response Model - Return Type · Extra Models · Response Status Code · Body - Updates ·
Advanced Python Types · Using Dataclasses (annexe) · Form Data / Form Models / Request Files
(annexe) · How-To « Separate OpenAPI Schemas for Input and Output or Not » · How-To
« Migrate from Pydantic v1 to v2 » (annexe).

## Plan

1. Pourquoi séparer `Create` / `Update` / `Read` (et quand un modèle unique suffit).
2. `response_model`, `response_model_exclude_unset`, filtrage des champs sensibles.
3. Validation avancée : `field_validator`, `model_validator`, types contraints, `Annotated`.
4. Types riches : `EmailStr`, `AnyUrl`, `AwareDatetime`, `UUID`, `Decimal`, énumérations.
5. Modèles imbriqués et listes de modèles.
6. Le `PATCH` correct : « null explicite » vs « champ absent », `exclude_unset` / `exclude_none`.
7. Paramètres groupés en modèles (query/cookie/header models).
8. Exemples de doc (`json_schema_extra`, `examples=`).
9. Introduction au versionnage des schémas.

## Exercices (aperçu)

- Éclater le modèle `Task` en schémas dédiés + champ calculé en sortie (`is_overdue`).
- Implémenter un `PATCH` gérant correctement les `null` explicites.
- Ajouter des sous-ressources imbriquées (`Task` avec `checklist: list[ChecklistItem]`).
- Regrouper les filtres de `GET /tasks` dans un `TaskFilters` (query model).
- **Mini-projet `linkstash`** (voir [`../projets/`](../projets/)).

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md#module-02--modélisation--validation-des-données-).

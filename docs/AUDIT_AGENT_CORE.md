# Audit — Partie Agent Core

> Audit de conformité de `student/agent_core/` (+ `student/agent_mbpp/task.py`, `student/agent_swebench/task.py`, dépendances étroitement couplées) par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-20
> **Mise à jour du 2026-08-20** : `student/data_models/` (le contrat de données partagé, initialement dans le périmètre) a été démantelé pendant cette même session — voir « Corrigés ». Les modèles vivent maintenant dans `agent_core/schemas.py`, `agent_mbpp/task.py`, `agent_swebench/task.py`.
> **Périmètre** : `student/agent_core/` (tous fichiers, y compris `schemas.py`) + `student/agent_mbpp/task.py` + `student/agent_swebench/task.py`
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier/module, chacun justifié par référence au sujet, par mypy/flake8, ou par test réel. Même méthodologie que `AUDIT_SANDBOX.md`.

---

## ⚠️ État général : un seul module a du contenu réel

Sur les 5 fichiers d'`agent_core/`, seul `provider/` (LLM) a été implémenté. `loop.py`, `manual.py`, `parsing.py`, `sandbox_client.py` sont encore des stubs (docstring uniquement, aucune ligne de code) — c'est-à-dire que **la boucle agent elle-même n'existe pas encore**. Rien de ce qui suit n'a donc pu être testé de bout en bout (aucun appel LLM réel n'a été exécuté dans le cadre de cet audit — l'analyse s'appuie sur mypy, flake8, et la lecture du code).

---

## `agent_core/provider/` (`base.py` + `__init__.py`)

### ✅ Bon

1. **Rotation multi-clés via `litellm.Router`** — conforme à l'exigence du sujet (§V.6 : *"must support multiple API tokens per provider"*). `_get_keys_for_provider` lit `PROVIDER_API_KEY`/`PROVIDER_API_KEYS` (CSV) depuis l'environnement, `Router(routing_strategy="usage-based-routing", allowed_fails=2, cooldown_time=5)` gère le failover.
2. **`StepMetrics` construit directement à la source** (dans `get_response()`, juste après l'appel API) plutôt que reconstruit plus loin dans la boucle — c'est le seul endroit où `llm_gen.usage`/le timing réel existent, cohérent avec la séparation générique/spécifique posée pour tout le projet.
3. **`LLMError` distincte des erreurs LiteLLM brutes** pour le cas "aucune clé trouvée" — lève une exception claire et actionnable plutôt qu'un `IndexError`/`KeyError` opaque à ce stade précis.
4. **`AbstractLLM` (ABC)** — pose un vrai contrat d'interface pour "un provider", cohérent avec l'exigence multi-provider du sujet (§IV.2 : *"You must support multiple LLM providers and models"*), même si une seule implémentation concrète existe pour l'instant.
5. **Emplacement corrigé pendant cette session** — le fichier vivait initialement dans `agent_core/llm.py`, hors de la structure `provider(s)/` prévue dès le début du projet ; déplacé vers `agent_core/provider/base.py`, avec un dossier fantôme vide (`agent_core/provider/`, non suivi par git) qui traînait déjà à cet endroit.

### ❌ Mauvais

1. **Signature incompatible avec l'interface abstraite — confirmé par mypy, pas une supposition.**
   ```
   agent_core/provider/base.py:103: error: Signature of "get_response" incompatible with supertype "AbstractLLM"
   Superclass:  def get_response(self, step: int) -> StepMetrics
   Subclass:    def get_response(self, step: int, prompt: str) -> StepMetrics
   ```
   `prompt` est requis dans l'implémentation mais absent du contrat abstrait — un second provider qui respecterait scrupuleusement `AbstractLLM` telle quelle ne pourrait pas passer de prompt du tout.
2. **Aucun `try/except` autour de `self.__router.completion(...)`** — alors que `LLMError` existe déjà dans le fichier, rien ne l'utilise à cet endroit. Si tous les fallbacks du router s'épuisent, l'exception LiteLLM brute remonte telle quelle, contrairement à §IV.1 (*"All errors must be handled gracefully"*).
3. **Accès non protégé à des champs qui peuvent ne pas exister — 6 erreurs mypy distinctes**, pas juste une supposition théorique :
   ```
   error: Item "CustomStreamWrapper" of "ModelResponse | CustomStreamWrapper" has no attribute "usage"
   error: Item "CustomStreamWrapper" of "ModelResponse | CustomStreamWrapper" has no attribute "choices"
   error: Argument "api_url" to "StepMetrics" has incompatible type "Any | str | None"; expected "str"
   ```
   `stream=False` est passé explicitement, donc en pratique `llm_gen` est toujours un `ModelResponse` — mais rien dans le code ne l'affirme (pas d'assertion, pas de narrowing), donc si un jour le streaming est activé sans revoir ce code, ça plantera silencieusement en prod. `llm_gen._hidden_params["api_base"]` accède en plus à un attribut privé (préfixe `_`) dont la présence n'est pas garantie — s'il est absent, `None` est passé à un champ `StepMetrics.api_url` typé `str` (pas `str | None`), ce qui lèvera une `ValidationError` Pydantic à l'exécution.
4. **`self.__model_name.split('/')[1]` sans validation.** Si `model_name` ne contient pas de `/` (erreur de saisie, ex: `"gpt-4"` sans préfixe provider), `IndexError` non capturé — crash brut plutôt qu'un message clair, alors que le fichier vérifie déjà l'absence de clés API avec un message propre juste avant.
5. **Placeholders explicites, à corriger avant toute soumission réelle** : `sandbox_input`/`sandbox_output = "NOT IMPLEMENTED"`, et surtout `retries=9999999999` — cette valeur remonte telle quelle jusqu'à `SolutionOutput.steps` puis `solution.json` si rien ne change, et le sujet vérifie explicitement l'absence de valeurs fabriquées en soutenance (§VI.4).

**Non bloquant mais à noter** : pas de gestion des `stop_sequences` (mentionnée dans le découpage initial du projet pour ce fichier, absente ici) ; attributs en double underscore (`self.__model_name`) — déclenche le name mangling Python, plus défensif que nécessaire pour une simple convention "privé" (un seul underscore suffirait, style non-bloquant).

---

## `loop.py`, `manual.py`, `parsing.py`, `sandbox_client.py`

Tous les quatre sont encore des stubs — uniquement le docstring d'intention posé au tout début du projet, aucune implémentation.

| Fichier | Rôle prévu | État |
|---|---|---|
| `loop.py` | Boucle Thought→Code→Observation (§V.1) | ❌ Stub |
| `parsing.py` | Extraction du code depuis la sortie LLM, 4 formats (§V.1.2) | ❌ Stub |
| `sandbox_client.py` | Client générique vers le process `sandbox` (§V.1.3) | ❌ Stub |
| `manual.py` | Génération dynamique du manuel depuis les schémas MCP (§V.2.6) | ❌ Stub |

Point notable : **le sandbox lui-même (côté `student/sandbox/`) est fonctionnel et testé de bout en bout** (voir `AUDIT_SANDBOX.md`) — connexion MCP, restrictions, watchdog, relais `tool_call`, tout marche en conditions Docker réelles. Rien de tout ça n'est encore branché à un appel LLM réel : la pièce manquante est exactement cette boucle.

Depuis le 2026-08-20, `agent_mbpp/` et `agent_swebench/` ne sont plus des répertoires complètement vides — chacun contient un `task.py` (le modèle de tâche spécifique, déplacé depuis `data_models/`, voir plus bas) — mais toujours aucun CLI/`__main__.py`, donc les 3 commandes du §V.3.1/§V.4.1 restent inexistantes.

---

## `data_models/` — démantelé le 2026-08-20

*(Section conservée à titre d'historique — le paquet n'existe plus, voir « Corrigés » ci-dessous.)*

Ce package regroupait initialement les 4 modèles du contrat d'évaluation (`MBPPTaskInput`, `SWEBenchTaskInput`, `StepMetrics`, `SolutionOutput`), au prix d'une contradiction avec le découpage générique/spécifique posé au tout début du projet (`agent_core/schemas.py` prévoyait `StepMetrics`/`SolutionOutput` partagés, `MBPPTaskInput`/`SWEBenchTaskInput` spécifiques à chaque benchmark). Les 3 points positifs qu'il avait (package sans dépendance, `steps: list[StepMetrics]` bien typé, schémas alignés sur `moulinette.models_public`) s'appliquent maintenant à `agent_core/schemas.py` — voir la section dédiée plus bas.

### `agent_core/schemas.py` (nouveau, remplace `data_models/`)

#### ✅ Bon

1. **`TaskInput` comme simple marqueur, pas une fausse abstraction.** `MBPPTaskInput` et `SWEBenchTaskInput` ne partagent aucun nom de champ ni type (`task_id: int` vs `instance_id: str`) — plutôt que d'inventer des champs communs artificiels, `TaskInput` reste une classe vide, utile uniquement pour le typage générique côté `loop.py` (`def run(task: TaskInput, ...)`).
2. **Package toujours sans dépendance** (ni `sandbox`, ni le reste d'`agent_core`) — hérité de `data_models`, préservé après la restructuration.
3. **`SolutionOutput.steps: list[StepMetrics]`** avec agrégats (`total_requests`, `total_input_tokens`, `total_output_tokens`, `iterations`) — modélise correctement la relation "un `StepMetrics` par itération" attendue par le sujet.
4. **Schémas alignés avec `moulinette.models_public`** (mentionné explicitement dans le docstring) — réduit le risque de divergence silencieuse avec ce que la moulinette attend réellement en validation.
5. **`MBPPTaskInput`/`SWEBenchTaskInput` héritent explicitement de `TaskInput`** (`agent_mbpp/task.py`, `agent_swebench/task.py`) — la dépendance va dans le bon sens (spécifique → générique), jamais l'inverse. Vérifié : `issubclass(MBPPTaskInput, TaskInput)` et `issubclass(SWEBenchTaskInput, TaskInput)` retournent `True`.

#### ❌ Mauvais

Aucun point ouvert.

---

## Corrigés pendant cette session

| Point | Fichier | Correctif appliqué |
|---|---|---|
| `data_models/__init__.py` important via `from student.data_models.X import Y` — `student` n'est pas un package top-level une fois `student` installé comme paquet (seuls `sandbox`, `agent_core`, `data_models` le sont individuellement). Bloquait **tout** import de `data_models`, donc `agent_core.provider` aussi, dès qu'invoqué autrement qu'en script depuis la racine du dépôt. | `data_models/__init__.py` | Imports internes changés en `from data_models.X import Y`, cohérent avec la convention déjà utilisée dans `sandbox/`. Vérifié dans les deux contextes : `import data_models` (depuis `student/`) et `from student.data_models import X` (depuis la racine, utilisé par `mcp_tools_*.py`) fonctionnent tous les deux. |
| `agent_core/llm.py` — hors de la structure `provider(s)/` prévue dès le début du projet, faisait doublon avec un dossier `provider/` vide déjà présent (non suivi par git) | `agent_core/provider/base.py` (déplacé), `agent_core/provider/__init__.py` (rempli) | Contenu déplacé tel quel (aucune logique modifiée), `__init__.py` exporte `AbstractLLM`, `LLM`, `LLMError` |
| `data_models/` centralisait les 4 modèles du contrat, en contradiction avec le découpage générique/spécifique posé au début du projet (`agent_core/schemas.py` prévoyait `StepMetrics`/`SolutionOutput` partagés, `MBPPTaskInput`/`SWEBenchTaskInput` spécifiques) — contradiction déjà signalée dans `AUDIT_MBPP.md` | `agent_core/schemas.py` (recréé : `TaskInput`, `StepMetrics`, `SolutionOutput`), `agent_mbpp/task.py` (nouveau : `MBPPTaskInput`), `agent_swebench/task.py` (nouveau : `SWEBenchTaskInput`), `data_models/` supprimé | 3 imports mis à jour (`mcp_tools_mbpp.py`, `mcp_tools_swebench.py`, `provider/base.py`), `pyproject.toml` nettoyé. Vérifié dans les deux sens : import en paquet installé (`agent_mbpp.task`) et depuis la racine (`student.agent_mbpp.task`, utilisé par `mcp_tools_mbpp.py`) ; `mypy`/`flake8` sans nouvelle erreur ; `mcp_tools_mbpp.py` démarre sans `ModuleNotFoundError` |

---

## Priorités recommandées

Par ordre d'impact :

1. **Écrire `loop.py`** — rien ne peut tourner de bout en bout sans lui ; c'est la pièce qui relie `provider/` (fait) et `sandbox` (fait et testé)
2. **Corriger les 3 points mypy de `provider/base.py`** (signature, accès non protégés, `try/except` manquant) — vite fait vu que le sandbox a déjà établi le pattern (`except Exception` ciblé, pas de crash brut)
3. **Remplacer les placeholders `NOT IMPLEMENTED`/`retries=9999999999`** avant toute tâche réelle soumise à la moulinette
4. **`parsing.py`** ensuite — nécessaire dès que `loop.py` doit extraire du code d'une vraie réponse LLM
5. **`sandbox_client.py`** et **`manual.py`** — le sandbox expose déjà tout ce dont ils ont besoin (`container.py`/`session.py`/`mcp_bridge.py`), donc plutôt du branchage que de la conception nouvelle

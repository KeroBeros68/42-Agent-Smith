# Audit — Partie Agent Core

> Audit de conformité de `student/agent_core/` (+ `student/agent_mbpp/task.py`, `student/agent_swebench/task.py`, dépendances étroitement couplées) par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-20
> **Mise à jour du 2026-08-20** : `student/data_models/` (le contrat de données partagé, initialement dans le périmètre) a été démantelé pendant cette même session — voir « Corrigés ». Les modèles vivent maintenant dans `agent_core/schemas.py`, `agent_mbpp/task.py`, `agent_swebench/task.py`.
> **Périmètre** : `student/agent_core/` (tous fichiers, y compris `schemas.py`) + `student/agent_mbpp/task.py` + `student/agent_swebench/task.py`
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier/module, chacun justifié par référence au sujet, par mypy/flake8, ou par test réel. Même méthodologie que `AUDIT_SANDBOX.md`.

---

## ⚠️ État général : 4 modules sur 5 ont du contenu réel, branchés et testés bout en bout

`provider/` (LLM), `parsing.py` (format primaire seulement), `sandbox_client.py` et `loop.py` sont implémentés et branchés entre eux. Seul `manual.py` reste un stub.

**Premier test d'intégration réel effectué le 2026-08-21** : `loop.run()` contre un vrai conteneur Docker (tâche MBPP 282, `mcp_tools_mbpp.py` connecté en stdio réel, modèle `deepseek/deepseek-v4-flash` avec une vraie clé API) — 5 itérations, aucun crash, cleanup propre. Le pipeline complet (appel LLM → extraction de code → exécution sandbox → relais MCP → réinjection de l'observation) fonctionne réellement, pas seulement en théorie. Résultat notable : le LLM a régénéré la même définition de fonction 5 fois sans jamais appeler `run_tests`/`final_answer`, parce que le `system_prompt` de test (écrit à la main, `manual.py` n'existe pas) documentait le tool sans montrer d'exemple d'appel concret — confirme empiriquement l'avertissement du sujet (§V.1, lignes 202-207) sur l'écart entre un prompt vague et un prompt avec exemple de raisonnement structuré. Aucun bug de code trouvé par ce test ; la leçon retenue est pour `manual.py`, qui devra inclure un exemple concret d'appel de tool, pas seulement sa signature.

---

## `agent_core/provider/` (`base.py` + `__init__.py`)

### ✅ Bon

1. **Rotation multi-clés via `litellm.Router`** — conforme à l'exigence du sujet (§V.6 : *"must support multiple API tokens per provider"*). `_get_keys_for_provider` lit `PROVIDER_API_KEY`/`PROVIDER_API_KEYS` (CSV) depuis l'environnement, `Router(routing_strategy="usage-based-routing", allowed_fails=2, cooldown_time=5)` gère le failover.
2. **`StepMetrics` construit directement à la source** (dans `get_response()`, juste après l'appel API) plutôt que reconstruit plus loin dans la boucle — c'est le seul endroit où `llm_gen.usage`/le timing réel existent, cohérent avec la séparation générique/spécifique posée pour tout le projet.
3. **`LLMError` distincte des erreurs LiteLLM brutes** pour le cas "aucune clé trouvée" — lève une exception claire et actionnable plutôt qu'un `IndexError`/`KeyError` opaque à ce stade précis.
4. **`AbstractLLM` (ABC)** — pose un vrai contrat d'interface pour "un provider", cohérent avec l'exigence multi-provider du sujet (§IV.2 : *"You must support multiple LLM providers and models"*), même si une seule implémentation concrète existe pour l'instant.
5. **Emplacement corrigé pendant cette session** — le fichier vivait initialement dans `agent_core/llm.py`, hors de la structure `provider(s)/` prévue dès le début du projet ; déplacé vers `agent_core/provider/base.py`, avec un dossier fantôme vide (`agent_core/provider/`, non suivi par git) qui traînait déjà à cet endroit.

### ❌ Mauvais

Aucun point ouvert — les 3 points identifiés initialement (absence de `try/except` autour de `self.__router.completion(...)`, `split('/')[1]` non validé, placeholders `NOT IMPLEMENTED`/`retries=9999999999`) ont été corrigés le 2026-08-20, voir « Corrigés ».

**Non bloquant mais à noter** : pas de gestion des `stop_sequences` (mentionnée dans le découpage initial du projet pour ce fichier, absente ici) ; attributs en double underscore (`self.__model_name`) — déclenche le name mangling Python, plus défensif que nécessaire pour une simple convention "privé" (un seul underscore suffirait, style non-bloquant).

---

## `loop.py`

### ✅ Bon

1. **Accumulation d'historique de conversation au format OpenAI** (`messages: list[dict]`, `role`/`content`) plutôt qu'une string aplatie — le modèle garde le contexte complet des itérations précédentes, cohérent avec la signature `get_response(step, messages)` de `provider/base.py` (choix déjà validé — « option A »).
2. **Setup unique en dehors de la boucle** — l'instance `LLM(model_name)` (donc le `Router` et ses clés) n'est construite qu'une fois, pas reconstruite à chaque itération.
3. **Boucle Thought→Code→Observation réellement fermée** — `parsing.extract_code()` puis `sandbox_client.run_code()` sont maintenant appelés à chaque itération, et le résultat (`_format_observation`) est réinjecté comme message `role: "user"` : le LLM reçoit désormais une vraie Observation à l'itération suivante, pas seulement ses propres réponses en boucle.
4. **Détection de `final_answer` avec arrêt anticipé** (`break` si `response.get("type") == "final_answer"`) — conforme à « Iterate until the task is solved » (§III.1), au lieu de tourner systématiquement `max_iterations` fois.
5. **`metrics.sandbox_input`/`sandbox_output` renseignés avec de vraies valeurs** (le code extrait, l'observation formatée) plutôt que laissés à leurs défauts vides — c'est exactement ce que `provider/base.py` ne pouvait pas faire lui-même (voir « Corrigés », point sur les placeholders) et que le docstring de `sandbox_client.run_code()` annonçait comme la responsabilité de l'appelant.

### ❌ Mauvais

1. **Pas de limites cumulées** (tokens totaux, temps total) — seul `max_iterations` est un paramètre ; rien n'empêche une boucle de consommer un budget de tokens disproportionné avant d'atteindre `max_iterations`.
2. **`_format_observation` dupliquée en substance avec `repl._format_response`** — même logique (distinguer `result`/`error`/`final_answer`), deux implémentations légèrement différentes (préfixes/`\n` différents pour l'affichage humain vs le texte envoyé au LLM). Différence délibérée pour l'instant (les deux publics sont différents), mais à surveiller si elles divergent involontairement plus tard.
3. **`code is None` renvoie toujours le même message d'observation** (« No valid code block was found in your response. ») — pas de distinction avec le deuxième cas de feedback du sujet (§V.1 : « A code block was malformed but was interpreted anyway ») ; `parsing.extract_code()` lui-même n'a pas encore cette distinction (voir sa propre section « Mauvais », point 2).
4. **Arrêt sur `LLMError` silencieux** — `break` sans logguer ni exposer pourquoi la boucle s'est arrêtée ; le retour `list[StepMetrics]` seul ne permet pas de distinguer un arrêt propre (`final_answer`/`max_iterations`) d'un échec LLM. Accepté pour l'instant (déféré à l'assemblage futur de `SolutionOutput`), mais à garder en tête.

---

## `sandbox_client.py`

### ✅ Bon

1. **Retourne le dict brut** (`result`/`error`/`final_answer`) plutôt qu'une string déjà formatée — laisse le choix du format à `loop.py`, qui a le contexte du `step` courant ; évite de dupliquer la logique d'affichage déjà écrite pour un besoin différent dans `repl._format_response`.
2. **Réutilise `session.relay_tool_calls`** au lieu d'en écrire une copie — élimine la duplication qui serait sinon apparue entre ce fichier et `repl.py` (même motivation que `session.build_container`, voir `AUDIT_SANDBOX.md`).
3. **Respecte la séparation générique/spécifique** : `loop.py` n'a pas besoin d'importer `sandbox.container`/`sandbox.mcp_bridge` directement, seulement `sandbox_client.run_code`.

### ❌ Mauvais

1. **Jamais testé en conditions Docker réelles** — contrairement à `container.py`/`session.py` (testés de bout en bout, voir `AUDIT_SANDBOX.md`), ce fichier n'a été vérifié qu'avec mypy/flake8, pas avec un vrai `run_code()` contre un conteneur démarré.

---

## `parsing.py`

### ✅ Bon

1. **`None` explicite pour "aucun bloc trouvé"**, pas d'exception ni de chaîne vide — signal propre que `loop.py` pourra transformer en feedback pour le LLM (§V.1 : *"No valid code block was found in the model's response"*), sans deviner ni fabriquer un code vide qui planterait bêtement dans le sandbox.
2. **Testé contre des exemples réels, pas juste supposé correct** : l'exemple exact du sujet (ligne 619, prose + bloc de code), l'absence de bloc, la présence du marqueur `<end_code>` après le fence, et un bloc multi-lignes — les 4 cas extraient exactement ce qui est attendu.
3. **Robuste au marqueur `<end_code>`** sans le traiter spécifiquement — la regex s'arrête au premier ``` ``` ``` fermant, qu'`<end_code>` suive ou non ; cohérent avec le fait que c'est un `stop_sequence` API (§V.6, ligne 693-699), pas un token garanti présent dans le texte reçu.

### ❌ Mauvais

1. **Seul le format (a) du sujet est géré** — XML tool calls (b), JSON/Hermes tool calls (c), ReAct (d) sont listés dans le sujet mais absents ici. Déféré volontairement (premier passage bout en bout avec le format primaire avant d'ajouter les 3 autres), mais reste un vrai manque pour le multi-provider (§V.1 : *"handle different output formats ... to fit what the LLMs you use were trained on"*).
2. **Pas de distinction "bloc malformé mais interprété quand même"** — le sujet demande explicitement ce cas de feedback (§V.1) ; la regex actuelle ne détecte que présent/absent, pas "presque valide" (ex: fence non fermé, indentation cassée).
3. **`re.search` ne prend que le premier bloc** — si le LLM génère plusieurs blocs de code dans une même réponse, les suivants sont silencieusement ignorés, sans feedback à ce sujet.

---

## `manual.py`

| Fichier | Rôle prévu | État |
|---|---|---|
| `manual.py` | Génération dynamique du manuel depuis les schémas MCP (§V.2.6) | ❌ Stub |

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
| Signature de `get_response` incompatible avec `AbstractLLM` (`step` seul dans l'interface, `step, prompt` dans l'implémentation) | `agent_core/provider/base.py` | Les deux signatures alignées sur `get_response(step, messages: list[dict])` — `prompt: str` remplacé par une vraie liste de messages OpenAI-style, nécessaire de toute façon pour que `loop.py` puisse faire suivre l'historique de conversation qui s'accumule au fil des itérations. Vérifié : l'erreur mypy `Signature ... incompatible with supertype` a disparu. |
| 6 erreurs mypy sur des accès non protégés (`llm_gen.usage`, `.choices`, `._hidden_params["api_base"]`) — `llm_gen` peut être un `CustomStreamWrapper` sans ces attributs, et `api_url`/`llm_output` pouvaient recevoir `None` sur un champ `str` | `agent_core/provider/base.py` | `isinstance(llm_gen, ModelResponse)` explicite (lève `LLMError` sinon) plutôt qu'une hypothèse silencieuse liée à `stream=False`. Découverte en creusant : `usage` peut être **réellement** `None` à l'exécution même avec `stream=False` (confirmé en lisant le source LiteLLM, pas une simple lacune de stub) — `getattr(llm_gen, "usage", None)` avec fallback à `0` gère ce cas réel, pas juste l'erreur de type. `_hidden_params.get(...) or ""` et `.content or ""` couvrent les deux derniers champs. Vérifié : `mypy agent_core` passe à 0 erreur (8 fichiers). |
| Aucun `try/except` autour de `self.__router.completion(...)` — l'exception LiteLLM brute remontait telle quelle si tous les fallbacks du router s'épuisaient | `agent_core/provider/base.py` | `try/except Exception as e: raise LLMError(...) from e` autour de l'appel, cohérent avec §IV.1 et avec le pattern déjà utilisé pour l'absence de clés API. Vérifié : `mypy agent_core` → 0 erreur, `flake8 agent_core/provider/base.py` → 0 warning. |
| `self.__model_name.split('/')[1]` sans validation — `IndexError` brut si `model_name` ne contient pas de `/` | `agent_core/provider/base.py` | Garde ajoutée dans `__init__`, avant toute utilisation de `split`/`[0]`/`[1]` : `if "/" not in model_name: raise LLMError(...)`. Message explicite avec le format attendu (`"provider/model"`). |
| Placeholders `sandbox_input`/`sandbox_output = "NOT IMPLEMENTED"`, `retries=9999999999` dans `StepMetrics(...)` — valeurs fabriquées, interdites en soutenance (§VI.4) | `agent_core/provider/base.py` | Les 3 champs retirés de l'appel explicite à `StepMetrics(...)` : `get_response()` n'a de toute façon aucune visibilité sur l'exécution sandbox à ce stade (elle n'a pas encore eu lieu). Ils retombent sur leurs vrais défauts Pydantic (`""`, `""`, `0`) ; `loop.py` les renseignera après coup, une fois le code exécuté dans le sandbox (`StepMetrics` est un `BaseModel` mutable). |
| `loop.py`/`sandbox_client.py` étaient des stubs vides — rien ne reliait `provider/` au sandbox | `agent_core/loop.py` (nouveau : `run(model_name, system_prompt, max_iterations) -> list[StepMetrics]`), `agent_core/sandbox_client.py` (nouveau : `run_code(container, mcp_bridge, code) -> dict`) | Squelettes volontairement minimaux — seules les pièces déjà écrites (`provider/`, `sandbox.container`/`session`/`mcp_bridge`) sont utilisées ; pas de détection `final_answer`, pas d'assemblage `SolutionOutput`, tant que `parsing.py` n'existe pas (aurait forcé des valeurs `success`/`solution` fabriquées). Vérifié : `mypy sandbox agent_core` (0 erreur, `executor/` vérifié séparément par convention) et `flake8` (0 warning) sur les fichiers touchés. |
| `_relay_tool_calls` aurait été dupliquée entre `repl.py` et le nouveau `sandbox_client.py` | `sandbox/session.py` (fonction déplacée depuis `repl.py`, rendue publique : `relay_tool_calls`), `repl.py` (import mis à jour) | Extraite avant duplication plutôt qu'après — voir aussi `AUDIT_SANDBOX.md`, section `session.py`, pour le détail (comportement inchangé). |
| `sandbox_client.run_code()` sans `try/except` autour de `container.send()`/`relay_tool_calls()` — une perte de connexion au conteneur remontait brute jusqu'à `loop.py` | `agent_core/sandbox_client.py` | `try/except (ConnectionError, TimeoutError)` autour de l'appel, remballé dans le même format que `protocol.ErrorMessage` (`type, error_type, message, traceback`) plutôt qu'un type de retour différent — `loop.py` n'aura jamais à distinguer "erreur du code exécuté" de "connexion perdue", les deux sont des `dict` de type `error`. Vérifié : `mypy sandbox agent_core` (0 erreur) et `flake8 agent_core/sandbox_client.py` (0 warning). |
| `agent_core/parsing.py` était un stub — aucun moyen d'extraire du code exécutable depuis `metrics.llm_output` | `agent_core/parsing.py` (nouveau : `extract_code(llm_output) -> str \| None`) | Format primaire du sujet seulement (blocs ```` ```python ... ``` ````), formats (b)/(c)/(d) déférés. `None` explicite si aucun bloc trouvé (§V.1). Testé contre l'exemple réel du sujet, l'absence de bloc, le marqueur `<end_code>`, et un bloc multi-lignes — 4/4 corrects. |
| `loop.py`/`parsing.py`/`sandbox_client.py` existaient mais n'étaient jamais appelés ensemble — la boucle Thought→Code→Observation n'était pas fermée (aucun message `role: "user"` jamais ajouté) | `agent_core/loop.py` | `run()` prend maintenant `container`/`mcp_bridge` en paramètres, appelle `extract_code()` puis `run_code()` à chaque itération, réinjecte l'observation formatée (`_format_observation`) comme message `role: "user"`, s'arrête sur `final_answer`. Vérifié : `mypy sandbox agent_core` (0 erreur) et `flake8 agent_core/loop.py` (0 warning). |
| `llm.get_response()` appelé sans `try/except` dans `loop.py` — un `LLMError` à l'itération *n* faisait planter tout `run()`, perdant les `StepMetrics` des itérations 1 à *n-1* | `agent_core/loop.py` | `try/except LLMError: break` autour de l'appel — sort proprement de la boucle en gardant les `steps` déjà accumulés au lieu de tout perdre. Limite connue documentée dans le docstring plutôt que cachée : le retour ne permet pas encore de distinguer un arrêt propre d'un échec (déféré à l'assemblage futur de `SolutionOutput`). Vérifié : `mypy sandbox agent_core` (0 erreur) et `flake8 agent_core/loop.py` (0 warning). |

---

## Priorités recommandées

Par ordre d'impact :

1. **`manual.py`** — génération du system prompt depuis les schémas MCP, **avec au moins un exemple concret d'appel de tool** (pas seulement sa signature) : le premier test d'intégration réel (voir ci-dessus) montre que sans exemple, le LLM ne déclenche jamais `run_tests`/`final_answer` et boucle sur la même réponse. Garder en tête le risque de double `list_tools()` avec `session.build_container()` (voir échange précédent).
2. **Assembler `SolutionOutput`** — côté `agent_mbpp`/`agent_swebench` (les deux CLI n'existent pas encore, voir plus bas), en enveloppant `loop.run()`
3. **Distinguer "aucun bloc trouvé" de "bloc malformé mais interprété"** dans `parsing.py`/`loop.py` (2e cas de feedback explicite du sujet, §V.1) — actuellement seul le premier cas existe
4. **Formats (b)/(c)/(d) de `parsing.py`** (XML, JSON/Hermes, ReAct) — une fois le format primaire prouvé bout en bout avec un vrai LLM (fait pour (a))

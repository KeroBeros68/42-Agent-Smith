# Audit — Partie Agent Core

> Audit de conformité de `student/agent_core/` (+ `student/agent_mbpp/task.py`, `student/agent_swebench/task.py`, dépendances étroitement couplées) par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au `CAHIER_DES_CHARGES.md`.
>
> **Date de l'audit** : 2026-08-20
> **Mise à jour du 2026-08-20** : `student/data_models/` (le contrat de données partagé, initialement dans le périmètre) a été démantelé pendant cette même session — voir « Corrigés ». Les modèles vivent maintenant dans `agent_core/schemas.py`, `agent_mbpp/task.py`, `agent_swebench/task.py`.
> **Périmètre** : `student/agent_core/` (tous fichiers, y compris `schemas.py`) + `student/agent_mbpp/task.py` + `student/agent_swebench/task.py`
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier/module, chacun justifié par référence au sujet, par mypy/flake8, ou par test réel. Même méthodologie que `AUDIT_SANDBOX.md`.

---

## ⚠️ État général : les 5 modules ont du contenu réel, branchés et testés bout en bout via une vraie CLI

`provider/` (LLM), `parsing.py` (format primaire seulement), `sandbox_client.py`, `loop.py` et `manual.py` sont tous implémentés et branchés entre eux. Depuis le 2026-08-26, `agent_mbpp/__main__.py` existe et a produit un `solution.json` valide (`success: true`) via la commande exacte du sujet (§V.3.1) — voir `AUDIT_MBPP.md` pour le détail de ce fichier.

**Premier test d'intégration réel effectué le 2026-08-21** : `loop.run()` contre un vrai conteneur Docker (tâche MBPP 282, `mcp_tools_mbpp.py` connecté en stdio réel, modèle `deepseek/deepseek-v4-flash` avec une vraie clé API) — 5 itérations, aucun crash, cleanup propre. Le pipeline complet (appel LLM → extraction de code → exécution sandbox → relais MCP → réinjection de l'observation) fonctionne réellement, pas seulement en théorie. Résultat notable : le LLM a régénéré la même définition de fonction 5 fois sans jamais appeler `run_tests`/`final_answer`, parce que le `system_prompt` de test (écrit à la main) documentait le tool sans montrer d'exemple d'appel concret.

**Rejoué le 2026-08-26 avec le manuel généré par `manual.py`** (`build_manual(tools)` au lieu du texte écrit à la main, incluant l'exemple d'appel synthétisé) : **résultat strictement identique** — le LLM redéfinit la fonction 5 fois, aucun appel à `run_tests`/`final_answer`. L'hypothèse du 2026-08-21 (« un exemple de syntaxe d'appel suffit ») est donc **infirmée empiriquement**, pas confirmée. Diagnostic affiné : `manual.py` documente correctement *comment appeler* un tool isolément, mais rien dans le prompt ne montre un **exemple complet du raisonnement en boucle** (Thought → Code qui écrit *et teste* la fonction dans le même bloc → Observation → Thought → `final_answer`) — exactement ce que le sujet demande séparément (§V.1 point 6 : *"examples of effective agent reasoning loops"*, distinct de la doc des tools). Ce manque relève du prompt d'orchestration assemblé par l'appelant, pas de `manual.py` dont le périmètre reste correctement limité à la doc des tools (§V.2.6).

**Rejoué une 3e fois le 2026-08-26** avec un exemple de boucle complète ajouté au prompt (Thought → Code qui définit *et* `print(run_tests(...))` → Observation → Thought → `final_answer`, sur une tâche jouet différente pour éviter la copie littérale) et l'exemple généré par `manual.py` corrigé (`print(tool(...))` au lieu de `result = tool(...)`, qui ne produisait aucune sortie stdout observable). **Résultat partiel** : à l'étape 5, le LLM appelle enfin `final_answer(...)` et `loop.py` s'arrête correctement dessus — première vérification réelle de ce chemin avec un vrai LLM (jusqu'ici seulement testé en théorie). **Mais `run_tests` n'est toujours jamais appelé** — le LLM répète la définition 4 fois puis soumet directement sans vérification. L'exemple de boucle a donc débloqué `final_answer`, pas la discipline « tester avant de soumettre ».

**Rejoué une 4e fois le 2026-08-26** avec une instruction explicite ajoutée au prompt (« you must call run_tests and see it pass before calling final_answer »). **Premier run complet et correct de bout en bout** : le LLM explore (étape 1, s'auto-teste avec un `print` direct), appelle `run_tests` et voit passer les tests (étape 2), re-écrit le code (étape 3), puis soumet avec `final_answer` (étape 4) — la boucle s'arrête d'elle-même après vérification. En creusant ce run, un bug distinct a été trouvé et corrigé côté `mcp_bridge.py` (`call_tool()` renvoyait l'objet `CallToolResult` complet plutôt que son `.data` — voir `AUDIT_SANDBOX.md`) : sans ce fix, l'observation de `run_tests` était le repr Python brut de l'objet plutôt que `"All test passed successfully !"`. Le pipeline complet (LLM → parsing → sandbox → tools MCP → boucle → `final_answer`) fonctionne donc désormais de bout en bout sur un cas réel, avec le texte d'observation propre.

---

## `agent_core/provider/` (`base.py` + `__init__.py`)

### ✅ Bon

1. **Rotation multi-clés via `litellm.Router`** — conforme à l'exigence du sujet (§V.6 : *"must support multiple API tokens per provider"*). `_get_keys_for_provider` lit `PROVIDER_API_KEY`/`PROVIDER_API_KEYS` (CSV) depuis l'environnement, `Router(routing_strategy="usage-based-routing", allowed_fails=2, cooldown_time=5)` gère le failover.
2. **`StepMetrics` construit directement à la source** (dans `get_response()`, juste après l'appel API) plutôt que reconstruit plus loin dans la boucle — c'est le seul endroit où `llm_gen.usage`/le timing réel existent, cohérent avec la séparation générique/spécifique posée pour tout le projet.
3. **`LLMError` distincte des erreurs LiteLLM brutes** pour le cas "aucune clé trouvée" — lève une exception claire et actionnable plutôt qu'un `IndexError`/`KeyError` opaque à ce stade précis.
4. **`AbstractLLM` (ABC)** — pose un vrai contrat d'interface pour "un provider", cohérent avec l'exigence multi-provider du sujet (§IV.2 : *"You must support multiple LLM providers and models"*), même si une seule implémentation concrète existe pour l'instant.
5. **Emplacement corrigé pendant cette session** — le fichier vivait initialement dans `agent_core/llm.py`, hors de la structure `provider(s)/` prévue dès le début du projet ; déplacé vers `agent_core/provider/base.py`, avec un dossier fantôme vide (`agent_core/provider/`, non suivi par git) qui traînait déjà à cet endroit.

**Depuis le 2026-08-26** : `LLM.__init__` accepte `provider_url: str | None = None`, transmis en `litellm_params["api_base"]` — comble un manque réel : `--provider-url` est un flag obligatoire de la CLI attendue par le sujet (§V.3.1/§V.4.1 : `--model-name "model/name" --provider-url "https://provider.api/v1"`), qui n'avait jusqu'ici aucun point d'entrée dans `provider/`. Optionnel et rétrocompatible (`None` par défaut, comportement inchangé pour les appels existants).

**Bug trouvé le 2026-08-26 en inspectant un vrai `solution.json`** : `request_time_ms=(end_time - start_time) / 1000` — `time.time_ns()` retourne des nanosecondes, diviser par `1000` donne des **microsecondes**, pas des millisecondes. Repéré parce qu'un appel API de quelques secondes affichait `request_time_ms: 3544313.675` (~59 min) dans le premier `solution.json` produit par le vrai CLI `agent_mbpp`. Corrigé en `/ 1_000_000`. Ce champ est cité dans `AUDIT_MBPP.md` comme support du §V.7 pt.3 (fiabilité provider, temps de réponse moyen) — avec ce bug, toute analyse de latence aurait été fausse d'un facteur 1000.

### ❌ Mauvais

Aucun point ouvert — les 3 points identifiés initialement (absence de `try/except` autour de `self.__router.completion(...)`, `split('/')[1]` non validé, placeholders `NOT IMPLEMENTED`/`retries=9999999999`) ont été corrigés le 2026-08-20, voir « Corrigés ».

**Non bloquant mais à noter** : pas de gestion des `stop_sequences` (mentionnée dans le découpage initial du projet pour ce fichier, absente ici) ; attributs en double underscore (`self.__model_name`) — déclenche le name mangling Python, plus défensif que nécessaire pour une simple convention "privé" (un seul underscore suffirait, style non-bloquant).

---

## `loop.py`

### ✅ Bon

1. **Accumulation d'historique de conversation au format OpenAI** (`messages: list[dict]`, `role`/`content`) plutôt qu'une string aplatie — le modèle garde le contexte complet des itérations précédentes, cohérent avec la signature `get_response(step, messages)` de `provider/base.py` (choix déjà validé — « option A »).
2. **Setup unique en dehors de la boucle** — l'instance `LLM(model_name)` (donc le `Router` et ses clés) n'est construite qu'une fois, pas reconstruite à chaque itération.
3. **Boucle Thought→Code→Observation réellement fermée** — `parsing.extract_code()` puis `sandbox_client.run_code()` sont maintenant appelés à chaque itération, et le résultat (`_format_observation`) est réinjecté comme message `role: "user"` : le LLM reçoit désormais une vraie Observation à l'itération suivante, pas seulement ses propres réponses en boucle.
4. **Détection de `final_answer` avec arrêt anticipé** (`break` si `response.get("type") == "final_answer"`) — conforme à « Iterate until the task is solved » (§III.1), au lieu de tourner systématiquement `max_iterations` fois. Depuis le 2026-08-26, le contenu soumis est aussi retourné (`tuple[list[StepMetrics], str | None]`) plutôt que seulement détecté en interne — testé avec un vrai LLM, `final_answer` remonte bien comme string exploitable par l'appelant.
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

### ✅ Bon

1. **Dynamiquement généré depuis les vrais schémas des tools, aucun nom codé en dur** — conforme au sujet (§V.2.6 : *"dynamically generated from the connected MCP server's tool schemas"*) ; testé contre le vrai `run_tests` de `mcp_tools_mbpp.py`, pas juste supposé correct.
2. **Inclut un exemple d'appel synthétisé, pas seulement la signature** (`_EXAMPLE_VALUES`, une valeur d'exemple par type JSON Schema) — motivé directement par le premier test d'intégration réel (2026-08-21, voir ci-dessus). **Réserve du 2026-08-26** : rejoué avec ce manuel seul, résultat identique (le LLM n'appelle toujours pas `run_tests`) — l'exemple de syntaxe d'appel isolé ne suffisait pas, il fallait un exemple de boucle de raisonnement complète (§V.1 point 6), hors du périmètre volontairement étroit de ce fichier. **Bug trouvé en écrivant cet exemple de boucle** : le format généré faisait `result = {tool}(...)` (assignation), qui ne produit **aucune sortie stdout observable** — même imité, l'observation serait restée vide. Corrigé en `print({tool}(...))`. Avec ce fix et l'exemple de boucle ajouté au prompt, `final_answer` est désormais appelé correctement (voir ci-dessus) — `run_tests` reste non appelé, mais ce n'est plus imputable à `manual.py`.
3. **Prend `tools: list[Any]` déjà récupéré plutôt qu'un `MCPBridge`** — n'appelle jamais `list_tools()` lui-même, évite le risque de double round-trip déjà identifié (en plus de celui que fait `session.build_container()`). Documenté explicitement dans la docstring plutôt que laissé implicite.
4. **Portée délibérément limitée à « the MCP tools doc »** (§V.2.6), pas tout le system prompt — le docstring précise la frontière avec les instructions Thought/Code/Observation (§V.1 point 6), qui restent la responsabilité d'un autre appelant.
5. **Cas `tools` vide géré explicitement** (`"No tools are available in this sandbox."`) plutôt qu'un manuel vide silencieux — même philosophie que `session.build_container()` pour `mcp_bridge is None`.

### ❌ Mauvais

1. **`_describe_tool` suppose `inputSchema.properties`** (même hypothèse que `session.build_container()`, voir `AUDIT_SANDBOX.md`) — un tool avec un schéma non-`object`/`$ref` ne casserait pas, mais produirait une signature/exemple vides plutôt qu'une vraie description.
2. **Un seul exemple générique par type, pas par tool** — `_EXAMPLE_VALUES["string"]` donne toujours `"..."`, même pour un paramètre qui attendrait spécifiquement du code Python (`code: str`) ; un exemple plus parlant (ex: un vrai extrait de code) aiderait sans doute davantage le LLM, mais nécessiterait une heuristique par nom de paramètre, pas seulement par type — déféré pour rester générique et sans connaissance codée en dur d'un tool particulier.

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
| `loop.run()` retournait seulement `list[StepMetrics]` — aucun moyen de savoir si/quoi `final_answer` avait soumis, nécessaire pour assembler `SolutionOutput.success`/`.solution` | `agent_core/loop.py` | Retour changé en `tuple[list[StepMetrics], str \| None]` — `final_answer` capturé directement depuis `response.get("answer", "")` au moment du `break`, `None` si la boucle s'arrête autrement (max_iterations, `LLMError`). Revérifié avec un vrai run LLM+Docker : `final_answer` remonte bien comme string exploitable. Vérifié : `mypy sandbox agent_core` (0 erreur) et `flake8 agent_core/loop.py` (0 warning). |
| `agent_core/manual.py` était un stub — aucune génération du manuel des tools pour le system prompt | `agent_core/manual.py` (nouveau : `build_manual(tools) -> str`) | Généré dynamiquement depuis `tool.name`/`tool.description`/`tool.inputSchema`, avec un exemple d'appel synthétisé par type JSON Schema — motivé par le résultat du premier test d'intégration réel (le LLM n'appelait jamais les tools sans exemple concret). Prend `tools` déjà récupéré plutôt qu'un `MCPBridge`, pour ne pas ajouter un second `list_tools()`. Testé contre le vrai `run_tests` de `mcp_tools_mbpp.py`. Vérifié : `mypy sandbox agent_core` (0 erreur) et `flake8 agent_core/manual.py` (0 warning). |
| `student/__init__.py` (fichier vide, tracké) rendait `student` importable comme un vrai package — en contradiction avec l'architecture documentée (« `student/` n'est pas un package »), et cassait `uv run mypy sandbox agent_core` pour **tout** le module, pas seulement `manual.py` (chaque fichier vu sous deux noms de module différents). Origine trouvée : `git show f411bfa --stat` affiche `BENCHMARK_REPORT.md => student/__init__.py` — un faux renommage détecté par git uniquement parce que les deux fichiers faisaient 0 octet ; le message du commit (« fix: exit(0)... ») ne mentionne aucun changement de packaging, donc très probablement un ajout accidentel | `student/__init__.py` (supprimé par l'utilisateur) | Vérifié après suppression : `uv run mypy sandbox agent_core` (sans `--explicit-package-bases`) repasse à 0 erreur (15 fichiers). |
| `LLM.__init__` n'acceptait pas d'URL de provider — `--provider-url` (flag obligatoire de la CLI attendue par le sujet, §V.3.1/§V.4.1) n'avait aucun point d'entrée dans `provider/` | `agent_core/provider/base.py` | `LLM(model_name, provider_url: str \| None = None)`, transmis en `litellm_params["api_base"]` dans `_setup_router()`. Optionnel, rétrocompatible. Vérifié : `mypy sandbox agent_core` (0 erreur) et `flake8 agent_core/provider/base.py` (0 warning). |
| `loop.run()` retournait seulement `list[StepMetrics]` — aucun moyen de savoir si/quoi `final_answer` avait soumis, nécessaire pour `SolutionOutput.success`/`.solution` | `agent_core/loop.py` | Retour changé en `tuple[list[StepMetrics], str \| None]`, `final_answer` capturé au moment du `break`. Revérifié avec un vrai run LLM+Docker. |
| `agent_mbpp/` n'avait pas de `__main__.py` — les 3 commandes CLI du §V.3.1 n'existaient pas | `agent_mbpp/__main__.py` (nouveau) | Parse `--task-file`/`--output`/`--model-name`/`--provider-url`/`--max-iterations`, injecte `MBPP_TASK_JSON` dans l'environnement avant `MCPBridge` (le serveur en a besoin dès son import), assemble le system prompt (manuel `manual.py` + instructions + exemple de boucle + obligation `run_tests` avant `final_answer` — le prompt qui a produit un run correct dans le script de test), appelle `loop.run()`, assemble `SolutionOutput` (`success = final_answer is not None`, heuristique simple assumée), écrit le résultat de façon atomique (fichier `.tmp` + `os.replace`, comble un point déjà noté dans `AUDIT_MBPP.md`). `SolutionOutput` initialisé avec des valeurs neutres avant le `try` pour qu'un crash produise quand même un `solution.json` valide avec `error` renseigné (§IV.1). **Testé de bout en bout avec la vraie commande du sujet** (`uv run python -m agent_mbpp --task-file ... --output ... --model-name "deepseek/deepseek-v4-flash"`, tâche MBPP 282 réelle) : `solution.json` produit, `success: true`, solution correcte et vérifiée par `run_tests` avant soumission, 3 itérations, traçabilité complète. |
| `request_time_ms=(end_time - start_time) / 1000` — `time.time_ns()` retourne des nanosecondes, `/1000` donne des microsecondes pas des millisecondes | `agent_core/provider/base.py` | Corrigé en `/ 1_000_000`. Trouvé en inspectant le premier `solution.json` réel produit par `agent_mbpp` (`request_time_ms: 3544313.675`, soit ~59 min pour un appel de quelques secondes) — pas en relisant le code. |
| `agent_swebench/` n'avait pas de `__main__.py` — les 3 commandes CLI du §V.4.1 n'existaient pas | `agent_swebench/__main__.py` (nouveau) | Même structure que `agent_mbpp/__main__.py` (§V.3.1), adaptée : `task.docker_image`/`build_context=None` (pull, pas de build local — §VII.2), `SWE_TASK_JSON`, `--max-iterations` par défaut 30 (§VI.1.2, vs 10 pour MBPP), prompt expliquant le workflow explorer→éditer→`run_tests()`→`get_patch()`→`final_answer(patch)`. Vérifié : `mypy sandbox agent_core agent_mbpp agent_swebench` (0 erreur) et `flake8` (0 warning). **Testé réellement le 2026-08-26** contre une vraie tâche Django (`django__django-15851`, pull d'une vraie image SWE-bench de 4,4 Go) : la CLI elle-même fonctionne parfaitement (tâche chargée, image pullée, conteneur démarré, 30 itérations LLM réelles, `solution.json` valide écrit, `success: false` correctement reporté, aucun crash) — mais **révèle un trou d'architecture majeur, sans rapport avec ce fichier** : les 9 tools MCP de `mcp_tools_swebench.py` échouent tous car `/testbed` n'existe que dans le conteneur Docker de la tâche, pas là où le serveur MCP s'exécute (sur l'hôte). Voir `AUDIT_SWEBENCH_TOOLS.md`, section dédiée, pour le détail et les pistes de correctif — non tranchées, décision d'architecture à prendre avant de rejouer ce test. |

---

## Priorités recommandées

Par ordre d'impact :

1. ~~**Écrire `agent_mbpp/__main__.py`**~~ **Fait le 2026-08-26** — testé de bout en bout avec la vraie commande du sujet, `solution.json` valide produit avec `success: true`. Détail de l'audit dans `AUDIT_MBPP.md` (périmètre plus adapté, cette CLI est spécifique MBPP).
2. **Distinguer "aucun bloc trouvé" de "bloc malformé mais interprété"** dans `parsing.py`/`loop.py` (2e cas de feedback explicite du sujet, §V.1) — actuellement seul le premier cas existe
3. **Formats (b)/(c)/(d) de `parsing.py`** (XML, JSON/Hermes, ReAct) — une fois le format primaire prouvé bout en bout avec un vrai LLM (fait pour (a))
4. **Affiner `success`** — actuellement `final_answer is not None`, sans vérifier que le dernier `run_tests` avant a bien réussi (l'agent pourrait soumettre après un test raté). Amélioration déjà notée dans `AUDIT_MBPP.md`.

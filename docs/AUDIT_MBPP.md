# Audit — Partie MBPP

> Audit de conformité de la partie MBPP par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au [Cahier des Charges](./CAHIER_DES_CHARGES.md).
>
> **Date** : 2026-08-20
> **Périmètre** : `mcp_tools_mbpp.py` (§V.3.2), les modèles du contrat d'évaluation — `student/agent_core/schemas.py`, `student/agent_mbpp/task.py`, `student/agent_swebench/task.py` (§V.3.3) —, `student/agent_core/` (§IV, §V.1, §V.3.1).
>
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier, justifiés par référence au sujet ou par un comportement observé. Les affirmations marquées « vérifié » ont été reproduites en lançant réellement le serveur MCP en stdio et en lui envoyant du JSON-RPC. Le sandbox (`student/sandbox/`) et les providers (`student/agent_core/provider/`) ne sont pas audités ici — voir `AUDIT_SANDBOX.md` et `AUDIT_AGENT_CORE.md`.
>
> **Corrections du 2026-08-20** : le commit `f411bfa` a enveloppé le test dans `try: {test} except SystemExit: sys.exit(1)` (couvre le `sys.exit` levé **pendant l'assertion**) et retiré le bloc DEBUG commenté (un `MBPPTaskInput` en dur) du chargement. Le commit `6288229` a ensuite injecté un patch `OS_EXIT_PATCH` qui remplace `os._exit` par `PATCH_EXIT → sys.exit(1)` avant d'exécuter le code soumis (l. 65, 86). Vérification refaite ici : **`os._exit(0)` est maintenant clos** (rc=1, avant : passait), et `sys.exit(0)` pendant l'assertion reste couvert. **Mais `sys.exit(0)` en tête de module passe toujours** (rc=0, vérifié) — il s'exécute avant le `try`, donc aucun `except` ne le rattrape, et le patch ne touche que `os._exit`. Le point ❌1 reste donc valide, réduit mais non clos, et sa partie la plus large (`os._exit`) est résolue. Le reste du document reflète l'état du dépôt à cette date.
>
> **Corrections du 2026-08-21** : le `try/except SystemExit` a été déplacé pour envelopper **tout le code soumis**, et non plus seulement l'assertion (`try:\n{indented_code}\n\n{test}`, l. 89-90), avec ré-indentation de chaque ligne du code (`indented_code`, l. 80) pour éviter un `IndentationError` sur les solutions multi-lignes ; un `\n` sépare désormais `test_imports` du patch (l. 89), réglant une concaténation qui rendait tout `test_imports` non vide syntaxiquement invalide. Vérification refaite ici : **`sys.exit(0)` en tête de module sort maintenant en rc=1** (avant : rc=0), et une solution honnête multi-ligne avec imports passe (rc=0). **Ce faux positif est donc entièrement clos** — `os._exit(0)` comme `sys.exit(0)`, où qu'il soit, échouent désormais. Toujours le 2026-08-21, le timeout par test ne dépend plus du nombre de tests : `timeout=TIMEOUT_DELAY_SEC` (10 s constant, l. 92) remplace `10 × len(test_list)` — le pire-cas passe de quadratique (10N² s) à linéaire (10N s), et ne déborde plus le budget global de 120 s (§VI.1.1) pour un nombre raisonnable de tests. **Le point ❌1 (timeout quadratique) est donc clos.** Toujours le 2026-08-21, l'échec de test renvoie désormais la cause : la dernière ligne de `proc.stderr` (type d'exception + message, ex. `NameError: name 'sub_list' is not defined`) est jointe au test fautif (l. 97-105), avec repli `exit code N, no stderr` quand la traceback est vide et une garde `[:300]` pour borner la réponse. Avant, seule la chaîne de l'assertion était renvoyée et les trois échecs diagnostiqués (TypeError, AssertionError, NameError) produisaient le même texte. **Le point ❌1 (feedback pauvre) est donc clos.** Toujours le 2026-08-21, une `MBPP_TASK_JSON` absente (ou invalide) se signale **dès le chargement** : un `print(..., file=sys.stderr)` (l. 39-42) avertit au boot, sur le canal stderr (séparé du flux JSON-RPC sur stdio, donc sans risque de corruption), tandis que `run_tests` continue de lever une `MBPPException` explicite à l'exécution. Dégradation gracieuse plutôt qu'un `exit` dur, ce qui préserve le lancement du serveur par le sandbox (`--mcp-stdio`). **Le point ❌1 (détection d'env var) est donc clos — le serveur MCP n'a plus de problème ❌.** Le reste du document reflète l'état du dépôt à cette date.
>
> **Correction du 2026-08-26** : le paragraphe ci-dessus (2026-08-21) est devenu **faux** sur un point précis. Le commit `f57ab82` (Gaspard, 2026-08-24, « feat: added run_tests() tool in SWEBench MCP Server » — un changement de dérive, sans rapport avec son propre message) a ajouté un `exit(1)` juste après le `print(..., file=sys.stderr)` (l. 45-52) : ce n'est **plus** une dégradation gracieuse. Vérifié empiriquement : `MBPP_TASK_JSON="not valid json" python3 mcp_tools_mbpp.py` sort en **rc=1** immédiatement, message sur stderr, plus de serveur du tout (avant : le process restait vivant, `run_tests` seul levait `MBPPException`). Conséquence en aval, testée aussi : `MCPBridge(...).connect()` contre un tel process ne bloque pas indéfiniment — il lève `McpError: Connection closed` après ~4 s — donc pas de hang silencieux, mais aucun code du dépôt (`cli.py`, `session.py`, `agent_core/loop.py`) n'a de `try/except` autour de `mcp_bridge.connect()` pour l'instant ; une tâche mal chargée ferait donc planter tout appelant avec cette trace peu explicite plutôt que le message clair qu'affiche le serveur sur son propre stderr. Le choix fail-fast lui-même est défendable (évite de brûler des itérations LLM sur un serveur qui ne pourra jamais répondre), donc pas classé ❌ ici — mais la conséquence côté sandbox est un vrai trou, documenté en 🟡 ci-dessous plutôt que dans `AUDIT_SANDBOX.md` pour garder la trace de cause à effet.
>
> **Mise à jour du 2026-08-27** : première validation avec la **moulinette officielle** (`uv sync` + `uv run moulinette_eval validate mbpp cache/mbpp_task.json cache/mbpp_solution.json`), pas seulement le `success: true` auto-déclaré par l'agent. Contre la vraie tâche 282 (`sub_list`, `deepseek/deepseek-v4-flash`, 2 itérations) : **Correctness: PASSED** (les 3 tests réels rejoués avec `skip_first_k_tests=0`, y compris le test caché jamais montré à l'agent lors de `dump`), **Metrics: VALID** (2/10 it., 899/6000 tokens entrée, 360/1500 sortie, 56.6s/120s), **Overall: PASSED**. Un premier essai avait donné `Correctness: FAILED` — cause trouvée : l'image Docker `python:3.11-slim` qu'utilise l'évaluateur de la moulinette n'était pas présente localement (`docker pull` suffit) ; pas un bug du projet.

---

## État général

Le contrat d'évaluation est en place : les trois modèles (`MBPPTaskInput`, `StepMetrics`, `SolutionOutput`) existent et reflètent `moulinette/models_public.py`. Le serveur MCP `mcp_tools_mbpp.py` est fonctionnel sur les deux transports et expose un outil `run_tests`. **Mise à jour du 2026-08-26** : la boucle agent générique (`agent_core/loop.py`) et son point d'entrée CLI (`agent_mbpp/__main__.py`) existent maintenant, sont branchés ensemble, et ont produit un `solution.json` valide (`success: true`) via la commande exacte du sujet contre un vrai LLM et un vrai conteneur Docker (voir `AUDIT_AGENT_CORE.md` et la section dédiée ci-dessous). **Ce n'est plus le trou principal de la partie.** Ce qui reste ouvert relève maintenant du raffinement (fiabilité du critère `success`, limites cumulées côté agent, fuite de secrets dans `run_tests`) plutôt que de pièces manquantes.

---

## `mcp_tools_mbpp.py` (racine) — serveur MCP (§V.3.2)

### ✅ Ce qui fonctionne

1. **La sortie du code testé ne peut pas corrompre le canal MCP.** `input=""` + `capture_output=True` (l. 93-94) absorbent le stdout du code généré et ferment son stdin immédiatement — critique sur un transport stdio, où le protocole JSON-RPC *est* stdout. Vérifié : un `print` dans le code soumis n'apparaît pas dans le flux et la réponse reste parsable. Le `input=""` couvre le cas symétrique d'un code qui appellerait `input()` et bloquerait le serveur.

2. **Le `test_list` vide ne produit plus un faux succès.** `if len(TASK.test_list) == 0` (l. 58) renvoie un message explicite au lieu de laisser la boucle ne rien faire et conclure « All test passed successfully ! ». Nuance : le message dit « You may skip testing », un assouplissement plutôt qu'une erreur dure — l'agent reste libre de rendre la main, mais il est *informé* au lieu d'être flatté d'un succès fantôme.

3. **Pré-vérification syntaxique par `compile()` avant tout lancement de processus** (l. 69). Le retour au LLM est catégoriquement distinct d'un échec de test (`SyntaxError` explicite, avec message et localisation), ce qu'exige le §V.1.3 ; on économise aussi N spawns de processus sur du code qui ne peut pas tourner ; et `compile()` ne fait que parser — il n'exécute rien, donc ce chemin est sûr même dans le processus serveur.

4. **Un processus par test, avec timeout individuel** (l. 83-102). Aucun état ne fuit d'un test au suivant ; un test qui boucle à l'infini ne masque pas le résultat des autres ; et le rapport d'échec est par test, grain utile pour le LLM. Le §V.2.5 précise que le timeout du sandbox ne s'applique pas aux actions du serveur MCP — l'outil devait avoir le sien, il en a un.

5. **Transport HTTP paramétrable par variable d'environnement** (l. 113-122). `MCP_TRANSPORT=http|stdio` pilote `mcp.run()`, avec validation explicite — une valeur invalide lève un `TypeError` clair au lieu d'échouer en silence. Cela couvre les deux transports exigés par le §V.2.5 et l'invocation `--mcp-server <URL>` du §V.2.1. Le `.env.example` documente la variable.

### ❌ Risques / problèmes

**Aucun problème ❌ restant sur ce fichier** — les quatre points d'exécution (faux positif, timeout quadratique, feedback, détection d'env var) sont clos (cf. blocs datés), et l'exécution sur l'hôte est reclassée en 🟡. La régression du 2026-08-24 sur l'`exit(1)` (voir bloc « Correction du 2026-08-26 ») est elle aussi classée en 🟡, pas ❌ — le choix fail-fast est défendable, seule sa conséquence côté sandbox (pas de `try/except` autour de `mcp_bridge.connect()`) est un vrai trou. Il ne reste que les points 🟡 de la section ci-dessous.

### 🟡 Points de conception à trancher (hors comptage)

- **`exit(1)` sur tâche absente/invalide (l. 52, ajouté le 2026-08-24) casse la connexion MCP plutôt que de dégrader gracieusement** — voir le bloc « Correction du 2026-08-26 » ci-dessus. Fail-fast défendable en soi, mais `mcp_bridge.connect()` n'est encadré d'aucun `try/except` nulle part dans le dépôt (`cli.py`, `session.py`, `agent_core/loop.py`) : une tâche mal chargée remonte comme `McpError: Connection closed` (~4 s, vérifié), pas le message clair que le serveur imprime sur son propre stderr. À trancher : soit revenir à la dégradation gracieuse (comme avant le 2026-08-24), soit ajouter le `try/except` manquant côté sandbox pour transformer l'échec de connexion en message actionnable.
- **L'exécution du code LLM sur l'hôte n'est pas une violation — mais l'héritage des secrets est à verrouiller.** Le §V.2.5 place explicitement les actions d'outils MCP « outside the sandbox », donc `subprocess.run([sys.executable, "-c", code])` (l. 85-96) est conforme à la spec ; câbler `SandboxContainer` ici serait lourd (un spawn Docker par test, à l'encontre du budget de temps tout juste réparé). Le seul vecteur concret est `load_dotenv()` (l. 26), qui charge les clés API du `.env` dans `os.environ` — processus enfant hérite intégralement, et il a le réseau. Correctif bon marché : ce serveur n'appelle pas l'API et ne lit que `MBPP_TASK_JSON` (posée par le sandbox), donc **supprimer `load_dotenv()`** suffit ; sinon, scruter l'`env=` passé à `subprocess.run`. Le prérequis sandbox du §IV.1 concerne la boucle agent, pas cet outil MCP.
- **Aucune ressource ni prompt MCP n'est exposé.** `resources/list` → `[]`, `prompts/list` → `[]` (vérifié). Le §V.2.5 énumère pourtant « MCP tools, resources, **and** prompts ». Peu coûteux à combler côté MBPP (une ressource `mbpp://task` exposant l'énoncé, un prompt de résolution), c'est une ligne du barème.
- **Le numéro de ligne du `SyntaxError` est décalé.** `compile()` reçoit `f"{imports}\n\n{code}"` (l. 69), donc la ligne rapportée est celle du texte concaténé, pas celle du code du LLM — décalage de +2 minimum, +2+len(test_imports) sinon. Vérifié : une erreur en ligne 1 du code soumis est annoncée « at line 3 ». Corriger en soustrayant l'offset avant de formater le message.
- **Un test qui passe ici ne garantit pas la validation.** La moulinette valide avec `skip_first_k_tests=0` (`moulinette/__main__.py:193`), c'est-à-dire **tous** les tests, alors que le `task.json` dumpé ne contient que `test_list[1:]` (`interact.py:210-211`). Un `success=True` fondé sur le seul verdict de `run_tests` est structurellement optimiste, et toute solution « collée » aux cas visibles sera prise en défaut — la garde-fou §VI.4.1 contre les solutions mémorisées. À dire dans le system prompt.
- **Divergence de version d'interpréteur.** `run_tests` exécute avec `sys.executable` (3.10, celui du projet) ; la moulinette valide dans `python:3.11-slim`. Rare mais réel comme source d'écart.

---

## `student/agent_mbpp/task.py` — `MBPPTaskInput` (§V.3.3)

### ✅ Ce qui fonctionne

1. **Correspondance champ par champ avec le contrat** (`moulinette/models_public.py:61-70`) : `task_id: int`, `task_definition`, `function_definition`, `test_imports`, `test_list` — mêmes noms, mêmes types, mêmes défauts. C'est ce qui permet à `mcp_tools_mbpp.py` de valider directement le JSON produit par `moulinette_eval dump mbpp` sans couche d'adaptation, vérifiable en quelques secondes en diffant les deux fichiers.

2. **Hérite de `TaskInput` (base commune dans `agent_core/schemas.py`)** — la boucle générique peut typer « une tâche » sans dépendre des champs spécifiques de MBPP ou SWE-bench. L'import `from agent_core.schemas import TaskInput` est plat, cohérent avec `sandbox/`.

3. **`default_factory=list` sur les deux champs de tests** — un `task.json` sans `test_imports` (cas majoritaire : la tâche 282 archivée a `"test_imports": []`) se parse sans cas particulier, et `default_factory` plutôt que `= []` évite le piège du défaut mutable partagé entre instances.

4. **Les quatre champs porteurs de sens sont obligatoires (`...`)** — un `task.json` tronqué lève une `ValidationError` au chargement au lieu de produire un objet à moitié vide. C'est ce qui donne du sens au `except ValidationError → TASK = None` du serveur MCP : sans obligation sur les champs, ce garde-fou ne se déclencherait jamais et l'outil tournerait sur une tâche fantôme.

5. **Syntaxe `list[str]` (PEP 585) et docstring traçant le §V.3** — cohérent avec `requires-python = "==3.10.*"`, sans imports `typing` superflus ; et un correcteur qui cherche « où sont les modèles imposés » trouve la réponse dès la première ligne du fichier (attente répétée du §VI.4 « Code quality, robustness »).

### ❌ Risques / problèmes

1. **`run_tests` ne vérifie pas que le code soumis définit bien `function_definition`.** Un message ciblé (« you didn't define `sub_list` ») serait plus utile que le `NameError` brut actuellement renvoyé par la traceback. (`function_definition` est désormais ancré dans le system prompt par `agent_mbpp/__main__.py` — voir « Corrigés » — donc ce point ne porte plus que sur `run_tests`.)

2. **Aucune contrainte au-delà du typage.** `task_id` peut être négatif, `test_list` peut être vide. Ce second cas n'est plus un faux succès à l'exécution (le serveur le garde, cf. ✅2), mais il serait plus propre de le détecter **au chargement** : `Field(min_length=1)` sur `test_list` déplacerait la détection là où elle est diagnosticable.

3. **Copie manuelle du contrat, sans garde anti-dérive.** Rien ne vérifie que ce fichier reste aligné sur `moulinette/models_public.py`. Si la moulinette évolue, l'écart ne se manifestera qu'à l'examen. Un test unique comparant `MBPPTaskInput.model_json_schema()` au modèle de référence transforme un risque silencieux en échec de CI.

4. **Aucun accesseur dérivé.** `mcp_tools_mbpp.py:78` fait déjà `"\n".join(TASK.test_imports)` à la main ; le futur constructeur de prompt refera le même travail pour `test_list`, et probablement différemment. Une propriété `test_preamble` / `public_tests_block` centralise la mise en forme et garantit que le LLM voit exactement ce que `run_tests` exécute — un écart entre les deux est une source d'itérations perdues difficile à diagnostiquer.

---

## `student/agent_swebench/task.py` — `SWEBenchTaskInput` (§V.4)

Hors périmètre strict de la partie MBPP, mais partage le même socle : hérite de `TaskInput`, `default_factory` sur `hints_text`/`repo`, champs obligatoires sur l'essentiel. `task_id` y est remplacé par `instance_id: str` — divergence voulue (MBPP = int, SWE-bench = str), qui confirme la justification de ne pas factoriser les champs dans `TaskInput`.

---

## `student/agent_core/schemas.py` — `StepMetrics` (§V.3.3)

### ✅ Ce qui fonctionne

1. **Les 11 champs du §V.3.3 sont présents, aux bons noms et bons types** — `step`, `input_tokens`, `output_tokens`, `request_time_ms`, `api_url`, `model_name`, `llm_output`, `sandbox_input`, `sandbox_output`, `retries`, `timestamp`. C'est ce tableau que le §VI.4.1 désigne comme le support de la traçabilité du raisonnement ; un champ manquant n'est pas une imprécision de forme, c'est la preuve d'absence de contournement qui disparaît.

2. **Défauts sur les champs de traçabilité, obligation sur les champs de mesure.** `llm_output`, `sandbox_input`, `sandbox_output`, `api_url`, `model_name`, `retries`, `timestamp` ont un défaut ; `step`, `input_tokens`, `output_tokens`, `request_time_ms` non. La ligne est tracée au bon endroit : une étape sans exécution sandbox reste enregistrable (§IV.1, aucune erreur ne doit faire tomber l'agent), mais on ne peut pas construire une étape en « oubliant » de mesurer la latence ou les tokens — or ce sont exactement les grandeurs que le §IV.2 rend obligatoires et que la moulinette contrôle.

3. **`request_time_ms: float` requis plutôt que défaut à 0.0** — un défaut aurait rendu le suivi de latence facultatif en pratique, alors que la fiabilité provider (temps de réponse moyen) est une section imposée du `BENCHMARK_REPORT.md` (§V.7 pt.3). Le modèle force la collecte à la source.

4. **`timestamp` en `default_factory` posé à la construction** — la chronologie est capturée sans effort côté appelant, et c'est elle qui rend calculables *a posteriori* les métriques intermédiaires du §V.7 pt.4. Sans horodatage par étape, ces analyses se refont à la main ou pas du tout.

5. **`retries` modélisé par étape et non seulement en total** — le §VI.1.3 interdit tout retry pendant l'examen, et le §V.7 pt.3 demande un décompte de retries par modèle. La granularité par étape sert les deux usages ; l'agrégat se recalcule, l'inverse non.

### ❌ Risques / problèmes

1. **Rien ne modélise les limites que ces métriques servent à respecter.** Les plafonds MBPP (10 itérations, 6 000 tokens d'entrée, 1 500 de sortie, 120 s — §VI.1.1) sont cumulatifs sur la tâche, et la moulinette les vérifie **après coup** (`MetricsValidationResult.validate_solution`). L'agent, lui, a besoin de la vérification **avant** d'envoyer la requête suivante. La moulinette expose un `MetricsLimits` (`moulinette/models.py`) qui n'a pas d'équivalent côté étudiant. C'est d'autant plus pressant que `loop.py` annonce une boucle « driven by … a limits config » dont la limite n'est, encore une fois, que documentée.

2. **Aucune distinction entre « 0 token » et « usage non rapporté ».** Les deux compteurs sont des `int` sans `Optional` ni sentinelle. Tous les providers gratuits ne renvoient pas le bloc `usage` (souvent absent en streaming) : le code d'intégration n'aura d'autre choix que d'écrire 0, ce qui **sous-estime** le cumul. La direction de l'erreur est la mauvaise — on croit respecter la limite alors qu'on la dépasse, et c'est la moulinette qui le découvre. Le §VI précise que les tokens de raisonnement comptent dans la limite, ce qui aggrave l'écart sur les modèles « reasoning ».

3. **`step` n'a pas de contrainte `ge=1` alors que sa description dit « 1-indexed ».** La description est de la documentation, pas une validation. Un décalage 0-indexed passerait silencieusement et fausserait toutes les métriques intermédiaires du §V.7 ainsi que la lecture du log. `Field(..., ge=1)` fait tenir la promesse.

4. **Aucune politique de troncature sur `llm_output` / `sandbox_output`.** Le §V.1.3 exige qu'une sortie tronquée pour cause de taille soit **signalée explicitement** au LLM. Ici les champs stockent la chaîne brute : rien ne tronque, rien ne marque qu'on a tronqué. Deux conséquences — `solution.json` peut gonfler sans borne, et le jour où la troncature sera implémentée dans la boucle, elle n'aura aucun endroit où le déclarer. Un champ booléen `truncated` (ou un suffixe normalisé) doit être décidé pendant que le format est encore libre.

---

## `student/agent_core/schemas.py` — `SolutionOutput` (§V.3.3)

### ✅ Ce qui fonctionne

1. **Structure identique au contrat, avec `steps: list[StepMetrics]` typé sur le vrai modèle** — la validation de `solution.json` par la moulinette contrôle en une passe l'enveloppe *et* chaque étape. Un `list[dict]` aurait laissé passer des étapes malformées jusqu'à l'analyse post-mortem.

2. **`error: str | None = None` : le chemin d'échec a une forme définie.** C'est ce qui permet à un agent qui abandonne (limite d'itérations atteinte, provider indisponible) de produire quand même un `solution.json` valide avec `success=False` et une cause lisible, au lieu de crasher. Le §IV.1 est explicite : « crashes during evaluation will result in failure » — un échec propre et documenté n'est pas la même chose qu'un crash.

3. **`system_prompt` présent.** Le §VI.4.1 en fait l'artefact de traçabilité qui prouve que l'agent n'a pas récupéré une solution mémorisée ou externe, et toute violation vaut 0. Le champ apparaît à une position différente dans le snippet du §V.3 et dans celui du §VI, ce qui le fait fréquemment oublier ; il est là.

4. **`task_id: str` conservé, alors que `MBPPTaskInput.task_id` est un `int`.** L'incohérence apparente est celle du contrat, pas du code : la moulinette écrit un `int` dans `task.json` et refait `int(task.task_id)` de son côté à la validation. Résister à l'envie de « corriger » le type est le bon choix — c'est le genre de divergence unilatérale qui casse une validation le jour de l'examen.

5. **Docstring qui nomme le fichier de sortie et ce que la moulinette en fait** — le lecteur sait immédiatement que ce modèle n'est pas une structure interne mais une interface externe, donc qu'on ne la modifie pas librement.

### ❌ Risques / problèmes

1. **`system_prompt` a un défaut vide alors que le sujet le rend obligatoire.** Le §V.4.2 le liste comme requis « pour une traçabilité complète du raisonnement », et le §VI.4.1 fait de cette traçabilité la pièce à conviction en cas de suspicion de solution mémorisée — sanction : 0. Avec `default=""`, un bug de câblage dans la boucle produit un `solution.json` parfaitement valide et totalement dépourvu de provenance, sans qu'aucune erreur ne soit levée. C'est le seul champ où être **plus strict** que le contrat ne coûte rien et supprime un risque à sanction maximale.

2. **Aucune validation croisée entre les totaux et les étapes.** Rien ne vérifie `total_input_tokens == sum(s.input_tokens for s in steps)`, ni `iterations == len(steps)`, ni `total_requests >= iterations`. Or la moulinette contrôle les **totaux** (`_print_metrics` lit `solution.total_*`) sans jamais les recouper avec `steps` : une erreur de comptabilité passe donc la validation, mais fausse toute l'analyse du `BENCHMARK_REPORT.md` (§V.7). Un `@model_validator(mode="after")` de quelques lignes rend l'incohérence impossible.

3. **`benchmark: str` libre plutôt que `Literal["mbpp", "swebench"]`.** Une faute de frappe (`"MBPP"`, `"mbpp "`) n'est détectée par rien côté étudiant. Côté moulinette, `_get_limits()` fait `sys.exit(1)` sur un benchmark inconnu : la tâche est perdue à la toute dernière étape, après avoir consommé le budget complet. Un `Literal` déplace l'échec à la construction de l'objet, c'est-à-dire avant. La présence de `SWEBenchTaskInput` rend le couple encore plus pressant : le champ `benchmark` n'existera plus pour rien.

4. **`success` n'est rattaché à aucune source de vérité.** Le champ est documenté « whether the agent believes it solved the task ». Combiné au fait que `success` est auto-déclaré par l'agent et au test caché rejoué à la validation (`skip_first_k_tests=0`), c'est le mode de défaillance le plus probable de toute la partie MBPP : l'agent se déclare gagnant et la moulinette dit non. Il faut décider et écrire la règle — `success=True` seulement si le dernier `run_tests` a répondu succès **et** que `final_answer` a été appelé avec ce code exact — plutôt que de laisser la boucle en décider au cas par cas. (`agent_mbpp/__main__.py` a depuis implémenté une règle plus simple, `final_answer is not None` — voir « Corrigés » — mais celle-ci ne ferme pas ce point : elle ne vérifie pas le dernier `run_tests`.)

---

## `student/agent_core/loop.py` — boucle agent (§V.1, §V.3.1)

> **Mise à jour du 2026-08-26** : ce qui suit décrivait `loop.py` comme un docstring sans corps — ce n'est plus le cas depuis les sessions du 2026-08-20/21, hors du périmètre initial de cet audit MBPP. Voir `AUDIT_AGENT_CORE.md` pour le détail complet ; résumé ici pour cohérence.

`agent_core/loop.py` existe et referme réellement la boucle « Thought → Code → Observation » : `run(container, mcp_bridge, model_name, system_prompt, max_iterations)` appelle `provider.LLM.get_response()`, `parsing.extract_code()`, `sandbox_client.run_code()` à chaque itération, réinjecte l'observation comme message `role: "user"`, et s'arrête sur `final_answer`. Testé de bout en bout le 2026-08-21 avec un vrai LLM (DeepSeek) et un vrai conteneur Docker + `mcp_tools_mbpp.py` connecté en stdio — aucun crash, cleanup propre. Point encore ouvert pour la partie MBPP :

- **Le respect des limites cumulées de tokens/temps (§VI.1.1) reste absent** — ni implémenté ni modélisé par un type (cf. ❌1 de `StepMetrics`, toujours valide). `--max-iterations` (§V.3.4, exposé en CLI) borne le nombre d'itérations, pas le budget tokens/temps consommé.

(Les 3 commandes CLI du §V.3.1 et le faux départ `student/__init__.py` sont résolus — voir « Corrigés » ci-dessous et `AUDIT_AGENT_CORE.md`.)

---

## `student/agent_mbpp/__main__.py` — point d'entrée CLI (§V.3.1)

> **Nouveau le 2026-08-26.**

### ✅ Bon

1. **Testé de bout en bout avec la commande exacte du sujet, pas une approximation** — `uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json --output ../cache/mbpp_solution.json --model-name "deepseek/deepseek-v4-flash"` (tâche 282 réelle) produit un `solution.json` valide : `success: true`, solution correcte, vérifiée par `run_tests` avant `final_answer`, 3 itérations, traçabilité complète (`system_prompt`, `steps`). **Confirmé par la moulinette officielle le 2026-08-27** (pas juste le `success` auto-déclaré) : `Correctness: PASSED` (3 tests réels rejoués, dont un caché), `Metrics: VALID`, `Overall: PASSED` — voir « Mise à jour du 2026-08-27 » en tête de document.
2. **`MBPP_TASK_JSON` injecté dans l'environnement avant `MCPBridge`** — `mcp_tools_mbpp.py` le lit à l'import, donc doit déjà être posé avant que le sous-processus démarre ; oublier cet ordre aurait fait échouer la connexion (`exit(1)`, voir bloc de correction du 2026-08-24 plus haut dans ce document).
3. **`SolutionOutput` initialisé avec des valeurs neutres avant le `try`** — un crash (Docker absent, `LLMError`, `ConnectionError`) produit quand même un `solution.json` valide avec `error` renseigné plutôt qu'un crash brut ou l'absence totale de fichier de sortie (§IV.1 : *"crashes during evaluation will result in failure"*, mais un échec documenté n'est pas un crash).
4. **Écriture atomique** (`.tmp` + `os.replace`) — comble le point ❌5 de la section `SolutionOutput` plus haut dans ce document (« Aucun utilitaire d'écriture »).
5. **Le prompt d'orchestration inclut l'obligation explicite de tester avant de soumettre** — pas seulement la doc des tools (`manual.build_manual`) ou un exemple de boucle, mais une instruction directe (« you must call run_tests ... before calling final_answer »). C'est ce qui a fait la différence lors des tests réels en amont (voir `AUDIT_AGENT_CORE.md`) : le manuel seul, puis le manuel + exemple de boucle, n'avaient pas suffi.

### ❌ Mauvais

1. **`success = final_answer is not None`** — ne vérifie pas que le **dernier** `run_tests` avant `final_answer` a effectivement réussi ; un agent pourrait soumettre après un échec de test (ou sans jamais tester, malgré l'instruction). C'est exactement le risque déjà identifié dans la section `SolutionOutput` ❌4 plus haut — toujours ouvert, non fermé par ce fichier.
2. **`--provider-url` non testé en conditions réelles** — le paramètre existe (`provider/base.py`) et est câblé, mais le test réel a utilisé DeepSeek sans le fournir (URL par défaut de LiteLLM). Le chemin `api_base` personnalisé reste vérifié seulement par mypy/flake8.
3. **Chemin d'échec testé, avec une nuance trouvée en le testant.** D'abord un bug réel : le `except (DockerException, LLMError, ConnectionError)` initial ne couvrait pas `mcp.shared.exceptions.McpError` (l'exception réellement levée par `mcp_bridge.connect()` sur une tâche mal chargée, vue plus tôt dans l'audit `AUDIT_MBPP.md`/`AUDIT_SANDBOX.md`) — un tel échec serait remonté en crash brut plutôt qu'un `solution.json` documenté. Élargi en `except Exception`, cohérent avec le rôle de frontière extérieure du programme (même pattern que `cli.py`, `KeyboardInterrupt`/`SystemExit` non capturées). **Testé réellement avec un `--model-name` invalide** : exit code 1, pas de traceback, `solution.json` valide produit (`success: false`, `steps: []`). **Mais `error` reste `null`** — `loop.py` capture déjà `LLMError` en interne (`try/except LLMError: break`, voir `AUDIT_AGENT_CORE.md`) pour préserver les `steps` déjà accumulés ; un échec dès la première itération ne laisse donc rien remonter jusqu'au `except Exception` de `__main__.py`. Comportement honnête (pas de crash, pas de valeur inventée) mais peu diagnostiquable — `loop.run()` pourrait à terme retourner aussi la raison de l'arrêt.

---

## Corrigés

Points résolus depuis leur signalement initial dans ce document — retirés des sections ❌/Priorités, listés ici pour la trace.

| Point | Fichier | Correctif appliqué | Date |
|---|---|---|---|
| `SolutionOutput` — aucun utilitaire d'écriture ; `--output` peut pointer vers un répertoire parent inexistant, et un `solution.json` interrompu en cours d'écriture serait corrompu | `agent_mbpp/__main__.py` (`write_output()`) | `output_path.parent.mkdir(parents=True, exist_ok=True)`, écriture dans un fichier `.tmp` puis `os.replace()` (atomique), `model_dump_json(indent=2)` | 2026-08-26 |
| `MBPPTaskInput.function_definition` n'était utilisé nulle part — le modèle ne voyait jamais la signature attendue | `agent_mbpp/__main__.py` (`build_system_prompt()`) | Ancré dans le system prompt (`Function signature: {task.function_definition}`) | 2026-08-26 |
| `agent_core/loop.py` docstring sans corps, aucun point d'entrée CLI — les 3 commandes du §V.3.1 n'existaient pas | `agent_core/loop.py`, `agent_mbpp/__main__.py` (nouveau) | Boucle Thought→Code→Observation fermée et testée de bout en bout avec un vrai LLM+Docker ; `__main__.py` teste avec la commande exacte du sujet, `solution.json` valide produit (`success: true`). Détail complet dans `AUDIT_AGENT_CORE.md` (« Corrigés ») | 2026-08-21 / 2026-08-26 |
| `max_iterations` (§V.3.4) non exposé en CLI | `agent_mbpp/__main__.py` | `--max-iterations` (défaut 10, §VI.1.1) | 2026-08-26 |
| `student/__init__.py` (fichier vide, ajout accidentel — voir `AUDIT_AGENT_CORE.md`) rendait `student` importable comme un vrai package et cassait `uv run mypy sandbox agent_core` | `student/__init__.py` (supprimé) | Détail complet dans `AUDIT_AGENT_CORE.md` (« Corrigés ») | 2026-08-26 |

---

## Architecture d'import / packaging

- `pyproject.toml` déclare quatre packages dans le wheel : `student/agent_core`, `student/agent_mbpp`, `student/agent_swebench`, `student/sandbox` — tous ont maintenant du contenu réel (le cas de packages vides est réglé). `uv build --wheel` réussit.
- Deux racines d'import coexistent : `mcp_tools_mbpp.py` importe `from student.agent_mbpp.task import MBPPTaskInput` (chemin `student.*`), tandis que `task.py` importe `from agent_core.schemas import TaskInput` (chemin top-level `agent_core.*`). Vérifié : les deux fonctionnent dans l'environnement courant. **Mais** le second suppose le paquet `student` installé (editable ou build) dans l'environnement qui lance le serveur — depuis une racine nue, `agent_core` n'est pas importable tel quel. C'est une contrainte opérationnelle à documenter dans la façon de lancer `mcp_tools_mbpp.py`.

---

## Récapitulatif de conformité §V.3

| Exigence | Réf. | État |
|---|---|---|
| CLI `python -m agent_mbpp` (`--task-file`, `--output`, `--model-name`, `--provider-url`) | §V.3.1 | ✅ **Existe et testée de bout en bout depuis le 2026-08-26** (`agent_mbpp/__main__.py`) — les 4 flags sont acceptés, `--provider-url` câblé mais non testé en réel (voir section dédiée) |
| Chargement de tâche + exécution agent | §V.3.1 | ✅ Les deux fonctionnent — vérifié avec la vraie tâche 282 via la commande exacte du sujet |
| Outil MCP `run_tests` | §V.3.2 | 🟡 Fonctionne ; `test_list` vide corrigé ; **faux positif entièrement clos** (`os._exit(0)` et `sys.exit(0)` où qu'il soit sortent en rc=1, vérifié) ; concaténation imports/patch réglée ; **timeout quadratique clos** (10 s constant par test, pire-cas linéaire) ; **feedback corrigé** (cause = dernière ligne de `stderr`) ; **env var manquante : détectée au démarrage mais sort en `exit(1)` depuis le 2026-08-24** (régression vs. dégradation gracieuse, casse la connexion MCP côté sandbox — voir 🟡 ci-dessus) |
| Ressources et prompts MCP exposés | §V.2.5 | ❌ `resources/list` et `prompts/list` vides (vérifié) |
| Transports stdio **et** HTTP | §V.2.5 | ✅ `MCP_TRANSPORT` env var |
| `mcp_tools_mbpp.py` à la racine | §V.2.5 | ✅ |
| Modèle `MBPPTaskInput` | §V.3.3 | ✅ Conforme au contrat |
| Modèle `StepMetrics` | §V.3.3 | ✅ Conforme au contrat |
| Modèle `SolutionOutput` | §V.3.3 | ✅ Conforme (`system_prompt` optionnel à durcir) |
| `max_iterations` configurable | §V.3.4 | ✅ `--max-iterations` (défaut 10) exposé en CLI depuis le 2026-08-26 |
| Respect des limites cumulées (10 it. / 6 000 / 1 500 / 120 s) | §VI.1.1 | ❌ Aucun mécanisme côté étudiant |
| Code LLM exécuté dans le sandbox | §IV.1 | 🟡 `run_tests` exécute sur l'hôte (vérifié) — permis par le §V.2.5 pour les outils MCP ; risque résiduel = héritage des secrets, verrouillable en supprimant `load_dotenv()` |
| Build du wheel (`packages` de `pyproject.toml`) | §VI | ✅ Réussit — les quatre packages ont du contenu |

---

## Priorités recommandées

Par ordre d'impact sur la note :

1. ~~**Écrire la boucle agent et ses points d'entrée**~~ **Fait le 2026-08-26** : `agent_core/loop.py` + `agent_mbpp/__main__.py` existent, branchés, testés de bout en bout avec un vrai LLM et un vrai conteneur Docker via la commande exacte du sujet — `solution.json` valide produit. C'est la condition de recevabilité du §V.3, désormais remplie.
2. **Affiner `success`** — `agent_mbpp/__main__.py` utilise `final_answer is not None`, sans vérifier que le **dernier** `run_tests` avant a réussi (voir section dédiée ci-dessus, et ❌4 de `SolutionOutput` plus haut, toujours ouvert).
3. **Verrouiller l'héritage des secrets dans `run_tests`** — supprimer `load_dotenv()` (l. 26 de `mcp_tools_mbpp.py`), qui charge les clés API du `.env` dans `os.environ` hérité intégralement par le processus enfant. L'exécution sur l'hôte est permise par le §V.2.5 pour les outils MCP (cf. 🟡) ; câbler `SandboxContainer` serait disproportionné (un spawn Docker par test). Supprimer l'appel ou scruter l'`env=` règle le seul vecteur concret en quelques lignes.
4. **Étendre le `try/except` de `mcp_bridge.connect()` à `cli.py`/`session.py`** — `agent_mbpp/__main__.py` l'a désormais (`except Exception`, testé réellement), mais le REPL interactif (`cli.py`) n'a toujours rien autour de sa propre construction de `MCPBridge` : une tâche mal chargée y remonterait encore comme `McpError: Connection closed` brut.
5. **Ajouter un garde-fou sur les limites cumulées côté agent** — un équivalent de `MetricsLimits`, vérifié *avant* chaque requête, pas seulement par la moulinette après coup. `--max-iterations` borne le nombre d'itérations, pas le budget tokens/temps.
6. **Nettoyage de conformité** : ressources/prompts MCP (`mbpp://task`, prompt de résolution), utilisation de `function_definition` dans le prompt et la vérification, ancrage de `system_prompt` comme obligatoire.

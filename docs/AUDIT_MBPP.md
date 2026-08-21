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
> **Corrections du 2026-08-21** : le `try/except SystemExit` a été déplacé pour envelopper **tout le code soumis**, et non plus seulement l'assertion (`try:\n{indented_code}\n\n{test}`, l. 89-90), avec ré-indentation de chaque ligne du code (`indented_code`, l. 80) pour éviter un `IndentationError` sur les solutions multi-lignes ; un `\n` sépare désormais `test_imports` du patch (l. 89), réglant une concaténation qui rendait tout `test_imports` non vide syntaxiquement invalide. Vérification refaite ici : **`sys.exit(0)` en tête de module sort maintenant en rc=1** (avant : rc=0), et une solution honnête multi-ligne avec imports passe (rc=0). **Ce faux positif est donc entièrement clos** — `os._exit(0)` comme `sys.exit(0)`, où qu'il soit, échouent désormais. Le reste du document reflète l'état du dépôt à cette date.

---

## État général

Le contrat d'évaluation est en place : les trois modèles (`MBPPTaskInput`, `StepMetrics`, `SolutionOutput`) existent et reflètent `moulinette/models_public.py`. Le serveur MCP `mcp_tools_mbpp.py` est fonctionnel sur les deux transports et expose un outil `run_tests`. En revanche, la **boucle agent n'existe pas** : `student/agent_core/loop.py` est un docstring sans corps, aucun `__main__.py` n'existe, et les trois commandes CLI du §V.3.1 ne peuvent donc pas s'exécuter. C'est le trou principal de la partie.

---

## `mcp_tools_mbpp.py` (racine) — serveur MCP (§V.3.2)

### ✅ Ce qui fonctionne

1. **La sortie du code testé ne peut pas corrompre le canal MCP.** `input=""` + `capture_output=True` (l. 93-94) absorbent le stdout du code généré et ferment son stdin immédiatement — critique sur un transport stdio, où le protocole JSON-RPC *est* stdout. Vérifié : un `print` dans le code soumis n'apparaît pas dans le flux et la réponse reste parsable. Le `input=""` couvre le cas symétrique d'un code qui appellerait `input()` et bloquerait le serveur.

2. **Le `test_list` vide ne produit plus un faux succès.** `if len(TASK.test_list) == 0` (l. 58) renvoie un message explicite au lieu de laisser la boucle ne rien faire et conclure « All test passed successfully ! ». Nuance : le message dit « You may skip testing », un assouplissement plutôt qu'une erreur dure — l'agent reste libre de rendre la main, mais il est *informé* au lieu d'être flatté d'un succès fantôme.

3. **Pré-vérification syntaxique par `compile()` avant tout lancement de processus** (l. 69). Le retour au LLM est catégoriquement distinct d'un échec de test (`SyntaxError` explicite, avec message et localisation), ce qu'exige le §V.1.3 ; on économise aussi N spawns de processus sur du code qui ne peut pas tourner ; et `compile()` ne fait que parser — il n'exécute rien, donc ce chemin est sûr même dans le processus serveur.

4. **Un processus par test, avec timeout individuel** (l. 83-102). Aucun état ne fuit d'un test au suivant ; un test qui boucle à l'infini ne masque pas le résultat des autres ; et le rapport d'échec est par test, grain utile pour le LLM. Le §V.2.5 précise que le timeout du sandbox ne s'applique pas aux actions du serveur MCP — l'outil devait avoir le sien, il en a un.

5. **Transport HTTP paramétrable par variable d'environnement** (l. 113-122). `MCP_TRANSPORT=http|stdio` pilote `mcp.run()`, avec validation explicite — une valeur invalide lève un `TypeError` clair au lieu d'échouer en silence. Cela couvre les deux transports exigés par le §V.2.5 et l'invocation `--mcp-server <URL>` du §V.2.1. Le `.env.example` documente la variable.

### ❌ Risques / problèmes

1. **Le timeout par test est quadratique : `10 × len(test_list)` *par processus*** (l. 92). Chaque test reçoit un budget de 10N s, donc un pire-cas total de **10N² s** — pour 5 tests, jusqu'à 250 s pour un seul appel d'outil, sur un budget global de 120 s (§VI.1.1). Le borne devrait s'appliquer au *total* cumulé, pas à chaque sous-processus. Il faut soit un budget global partagé (arrêt dès que le cumul dépasse un plafond), soit un timeout constant par test **et** un plafond global — la constante devrait venir de la configuration.

2. **Le code LLM est exécuté sur l'hôte, pas dans le sandbox construit.** `run_tests` fait `subprocess.run([sys.executable, "-c", code])` (l. 85-96) dans le cwd du serveur, avec l'environnement complet et le réseau, alors que `student/sandbox/` fournit déjà un conteneur `network_mode="none"`, `read_only`, `cap_drop=["ALL"]`, `mem_limit` (voir `AUDIT_SANDBOX.md`). La tension du §V.2.5 (« MCP tool actions happen outside the sandbox ») justifie que l'outil agisse sur l'hôte, mais ici l'outil ne fait *que* ré-exécuter le code LLM — il recrée donc un chemin d'exécution non contraint parallèle au sandbox. Risque concret : `load_dotenv()` (l. 26) charge les clés API de l'examen dans `os.environ`, que le processus enfant hérite intégralement — un code généré lisant `os.environ` et disposant du réseau est un vecteur d'exfiltration. La moulinette de référence, elle, exécute dans Docker (`moulinette/mbpp/interact.py:74`).

3. **L'échec de test ne dit pas *pourquoi* il échoue.** `proc.stdout` et `proc.stderr` sont capturés (l. 95) puis jetés ; seule la chaîne de l'assertion est renvoyée (l. 98-104). Vérifié : `return a-b` (TypeError), `return [0,0]` (AssertionError) et un code ne définissant pas la fonction (NameError) produisent **exactement le même texte**. C'est le point qui coûtera le plus d'itérations : le §V.1.3 impose un feedback explicite, et le budget est de 10 itérations et 6 000 tokens d'entrée cumulés (§VI.1.1). Renvoyer la dernière ligne de la traceback suffirait.

4. **La tâche n'est injectable qu'au démarrage, par variable d'environnement.** Rien dans le schéma de l'outil ne révèle cette dépendance : un correcteur qui lance le serveur à la main sans `MBPP_TASK_JSON` voit un `run_tests` qui échoue systématiquement sans indice sur la cause (le message d'erreur le dit, mais il faut lancer l'outil pour le lire). Un `--task-file` en argument de ligne de commande (en complément de l'env var) rendrait le serveur testable indépendamment, ce que le §V.5 exige pour les outils obligatoires.

### 🟡 Points de conception à trancher (hors comptage)

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

1. **`function_definition` n'est utilisé nulle part.** C'est pourtant la donnée la plus utile : le nom exact et la signature que la solution doit respecter (`def sub_list(nums1,nums2):`). Deux usages immédiats restent de côté — l'ancrer dans le system prompt pour que le modèle ne renomme pas la fonction, et vérifier dans `run_tests` que le code soumis définit bien ce nom, ce qui donnerait un message autrement plus exploitable que le `NameError` muet actuel (cf. ❌3 du serveur MCP).

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

4. **`success` n'est rattaché à aucune source de vérité.** Le champ est documenté « whether the agent believes it solved the task ». Combiné au fait que `success` est auto-déclaré par l'agent et au test caché rejoué à la validation (`skip_first_k_tests=0`), c'est le mode de défaillance le plus probable de toute la partie MBPP : l'agent se déclare gagnant et la moulinette dit non. Il faut décider et écrire la règle — `success=True` seulement si le dernier `run_tests` a répondu succès **et** que `final_answer` a été appelé avec ce code exact — plutôt que de laisser la boucle en décider au cas par cas.

5. **Aucun utilitaire d'écriture.** Le §V.3.1 impose un `--output ../cache/mbpp_solution.json` dont le répertoire parent n'existe pas forcément — la moulinette, elle, fait `output_path.parent.mkdir(parents=True, exist_ok=True)` avant d'écrire. Il manque le pendant côté étudiant (création du parent, `indent=2`, écriture atomique via fichier temporaire + `rename`). Un `solution.json` à moitié écrit parce que le processus a été interrompu, c'est une tâche perdue pour une raison sans rapport avec la qualité de l'agent.

---

## `student/agent_core/loop.py` — boucle agent (§V.1, §V.3.1)

**Le fichier est un docstring sans corps exécutable.** La boucle « Thought → Code → Observation » annoncée (drivée par un `TaskInput`, un config de limites, un provider LLM et une connexion sandbox, sans logique MBPP/SWE-bench) n'est pas écrite. Conséquences :

- **Aucune des trois commandes CLI du §V.3.1 ne s'exécute** : `python -m agent_mbpp` (et ses équivalents) nécessitent un `__main__.py` et une boucle derrière — ni l'un ni l'autre n'existe. C'est la condition de recevabilité du §V.3 qui saute, et c'est le plus gros écart de la partie.
- **`max_iterations` configurable (§V.3.4) et le respect des limites cumulées (§VI.1.1) sont absents** — non seulement non implémentés, mais sans même de type qui les modélise (cf. ❌1 de `StepMetrics`).
- **`student/__init__.py` existe** (paquet régulier, cohérent), mais cela ne fournit pas de point d'entrée.

---

## Architecture d'import / packaging

- `pyproject.toml` déclare quatre packages dans le wheel : `student/agent_core`, `student/agent_mbpp`, `student/agent_swebench`, `student/sandbox` — tous ont maintenant du contenu réel (le cas de packages vides est réglé). `uv build --wheel` réussit.
- Deux racines d'import coexistent : `mcp_tools_mbpp.py` importe `from student.agent_mbpp.task import MBPPTaskInput` (chemin `student.*`), tandis que `task.py` importe `from agent_core.schemas import TaskInput` (chemin top-level `agent_core.*`). Vérifié : les deux fonctionnent dans l'environnement courant. **Mais** le second suppose le paquet `student` installé (editable ou build) dans l'environnement qui lance le serveur — depuis une racine nue, `agent_core` n'est pas importable tel quel. C'est une contrainte opérationnelle à documenter dans la façon de lancer `mcp_tools_mbpp.py`.

---

## Récapitulatif de conformité §V.3

| Exigence | Réf. | État |
|---|---|---|
| CLI `python -m agent_mbpp` (`--task-file`, `--output`, `--model-name`, `--provider-url`) | §V.3.1 | ❌ Absente — pas de `__main__.py`, `loop.py` est un docstring |
| Chargement de tâche + exécution agent | §V.3.1 | ❌ Absent |
| Outil MCP `run_tests` | §V.3.2 | 🟡 Fonctionne ; `test_list` vide corrigé ; **faux positif entièrement clos** (`os._exit(0)` et `sys.exit(0)` où qu'il soit sortent en rc=1, vérifié) ; concaténation imports/patch réglée ; feedback pauvre |
| Ressources et prompts MCP exposés | §V.2.5 | ❌ `resources/list` et `prompts/list` vides (vérifié) |
| Transports stdio **et** HTTP | §V.2.5 | ✅ `MCP_TRANSPORT` env var |
| `mcp_tools_mbpp.py` à la racine | §V.2.5 | ✅ |
| Modèle `MBPPTaskInput` | §V.3.3 | ✅ Conforme au contrat |
| Modèle `StepMetrics` | §V.3.3 | ✅ Conforme au contrat |
| Modèle `SolutionOutput` | §V.3.3 | ✅ Conforme (`system_prompt` optionnel à durcir) |
| `max_iterations` configurable | §V.3.4 | ❌ Absent |
| Respect des limites cumulées (10 it. / 6 000 / 1 500 / 120 s) | §VI.1.1 | ❌ Aucun mécanisme côté étudiant |
| Code LLM exécuté dans le sandbox | §IV.1 | ❌ `run_tests` exécute sur l'hôte (vérifié), malgré un sandbox construit |
| Build du wheel (`packages` de `pyproject.toml`) | §VI | ✅ Réussit — les quatre packages ont du contenu |

---

## Priorités recommandées

Par ordre d'impact sur la note :

1. **Écrire la boucle agent et ses points d'entrée** (`loop.py` + `__main__.py` pour `agent_mbpp`) : aucune des trois commandes du §V.3.1 n'existe, et sans elle le reste du contrat est inutilisable. C'est la condition de recevabilité du §V.3.
2. **Faire passer l'exécution des tests par le sandbox existant** — réutiliser `SandboxContainer` (`network:none`, allowlist, `mem_limit`) dans `run_tests`, au lieu de `subprocess.run(sys.executable)` sur l'hôte. Le sandbox est construit ; l'écart est un non-câblage, pas un manque. Sans ce point, un correcteur démontre l'exfiltration en direct via les clés API chargées dans `os.environ`.
3. **Corriger le timeout global** — remplacer `10 × len(test_list)` *par processus* par un budget global (le pire-cas actuel de 10N² s fait déborder le 120 s §VI.1.1 dès 3-4 tests).
4. **Renvoyer la cause de l'échec** (dernière ligne de traceback) — le meilleur rapport gain/effort sur le budget de 10 itérations et 6 000 tokens.
5. **Ajouter un garde-fou sur les limites cumulées côté agent** — un équivalent de `MetricsLimits`, vérifié *avant* chaque requête, pas seulement par la moulinette après coup. C'est le prérequis pour que la boucle (priorité 1) ne dérape pas.
6. **Nettoyage de conformité** : ressources/prompts MCP (`mbpp://task`, prompt de résolution), utilisation de `function_definition` dans le prompt et la vérification, ancrage de `system_prompt` comme obligatoire.

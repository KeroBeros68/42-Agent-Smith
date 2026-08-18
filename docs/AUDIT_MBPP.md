# Audit — Partie MBPP

> Audit de conformité de la partie MBPP réalisée à ce jour, par rapport au sujet officiel (`subject-1-1.txt`, v1.1) et au [Cahier des Charges](./CAHIER_DES_CHARGES.md).
>
> **Date de l'audit** : 2026-08-16
> **Dernière révision** : 2026-08-16 — reflet de l'état du dépôt après les commits SWE-bench (`agent_core/` construit, `sandbox/` câblé, MCP SWE-Bench ajouté).
> **Périmètre** : `mcp_tools_mbpp.py` (§V.3.2), `student/data_models/` (§V.3.3), `student/agent_core/` et `student/sandbox/` (§IV, §V.2)
> **Méthode** : 5 points positifs max et 5 points négatifs max par fichier, chacun justifié par référence au sujet **ou par un comportement observé** — chaque affirmation marquée « vérifié » a été reproduite en lançant réellement le serveur MCP en stdio et en lui envoyant du JSON-RPC.

---

## ⚠️ Préambule : deux constats structurants (évolution depuis le 14/08)

**1. `student/agent_mbpp/` n'existe plus — et `pyproject.toml` le déclare toujours comme package.** La branche a remplacé les deux répertoires vides par un `student/agent_core/` partagé (loop, parsing, sandbox_client, manual, providers), mais tous ces fichiers restent des docstrings-squelettes : `loop.py` n'a toujours aucun corps exécutable, aucun `__main__.py` n'existe nulle part, et les trois commandes du §V.3.1 ne s'exécutent toujours pas. Pire qu'au 14/08 : `pyproject.toml:32-33` déclare `student/agent_mbpp` et `student/agent_swebench` dans `[tool.hatch.build.targets.wheel] packages`, or ces répertoires **n'existent pas sur disque** — la construction du wheel (`pip install .` / `uv build`) échoue sur le paquet absent. La déclaration est passée d'« inerte mais vraie » (répertoire vide) à « fausse » (répertoire disparu).

**2. Le sandbox est construit, mais `run_tests` ne s'en sert pas.** `student/sandbox/` est désormais un vrai bac à sable Docker — `container.py` lance un conteneur `network_mode="none"`, `read_only=True`, `cap_drop=["ALL"]`, `pids_limit`, `mem_limit`, tmpfs sur `/workspace` et `/tmp` ; `executor/restrictions.py` fait une allowlist d'imports stdlib ; `executor/watchdog.py` borne chaque snippet ; `mcp_bridge.py` relaie les `tool_call` du conteneur vers le serveur MCP. C'est exactement l'architecture que §IV.1 et §V.2.5 décrivent.

Or `run_tests` (`mcp_tools_mbpp.py:95-97`) exécute toujours le code du LLM **sur l'hôte** via `subprocess.run([sys.executable, "-c", code])`, dans le cwd du serveur, avec l'environnement complet du parent et le réseau. Vérifié : un `code` contenant `open('/tmp/mbpp_sandbox_escape.txt','w').write('escaped')` crée bien le fichier sur l'hôte. Le sandbox et la moulinette (`moulinette/mbpp/interact.py:74`, `run_code_in_docker`, `network_disabled=True`, `mem_limit="128m"`) prennent tous deux la précaution que `run_tests` ignore.

La tension du §V.2.5 (« MCP tool actions happen outside the sandbox ») justifie que l'outil MCP agisse sur l'hôte, mais ici l'outil ne fait **que** ré-exécuter le code LLM — il recrée donc un chemin d'exécution non contraint parallèle au sandbox qui vient d'être construit. **La première priorité s'est déplacée** : il ne s'agit plus de « construire un sandbox », il est là — il s'agit de faire passer l'exécution des tests par lui (ou par `SandboxContainer`), ou de supprimer l'exécution du code de l'outil pour la laisser au sandbox. Risque concret inchangé : `load_dotenv()` (`mcp_tools_mbpp.py:26`) charge les clés API de l'examen dans `os.environ`, que le processus enfant hérite intégralement — un code généré lisant `os.environ` et disposant du réseau est un vecteur d'exfiltration.

---

## `mcp_tools_mbpp.py`

### ✅ Bon

1. **La sortie du code testé ne peut pas corrompre le canal MCP.** `capture_output=True` + `input=""` (lignes 98-100) : le stdout du code généré est absorbé, et son stdin est fermé immédiatement. C'est loin d'être un détail sur un transport stdio — le protocole JSON-RPC *est* stdout. Vérifié : un `print('hello from LLM code')` dans le code soumis n'apparaît pas dans le flux et la réponse reste parsable. Le `input=""` couvre le cas symétrique : un code appelant `input()` bloquerait le serveur jusqu'au timeout au lieu de rendre la main.

2. **Le faux positif du `test_list` vide est corrigé** (lignes 75-77). Au 14/08, un `test_list: []` produisait « All test passed successfully ! » — la boucle ne s'exécutait pas et `failed_tests` restait vide. Désormais `if len(TASK.test_list) == 0` renvoie un message explicite au lieu de valider. Nuance : le message dit « You may skip testing », un assouplissement plutôt qu'une erreur dure — l'agent peut encore choisir de rendre la main, mais il est au moins *informé* au lieu d'être flatté d'un faux succès. C'est une correction nette de la classe entière de faux positifs.

3. **Pré-vérification syntaxique par `compile()` avant tout lancement de processus** (lignes 84-90). Trois bénéfices distincts : le retour au LLM est *catégoriquement* différent d'un échec de test (`SyntaxError` explicite, avec message et localisation), ce qu'exige le §V.1.3 ; on économise N spawns de processus sur du code qui ne peut pas tourner ; et `compile()` ne fait que parser, il n'exécute rien, donc ce chemin est sûr même dans le processus serveur. Vérifié : `def sub_list(a, b)` sans `:` renvoie `SyntaxError in the submitted code: expected ':' […]` plutôt qu'une liste de tests échoués.

4. **Un processus par test, avec timeout individuel** (lignes 93-104). Trois propriétés qu'une exécution groupée n'aurait pas : aucun état ne fuit d'un test au suivant ; un test qui boucle à l'infini ne masque pas le résultat des autres ; et le rapport d'échec est par test, grain utile pour le LLM. Le §V.2.5 précise que le timeout du sandbox **ne** s'applique **pas** aux actions du serveur MCP — l'outil devait avoir son propre timeout, il en a un.

5. **Le transport HTTP est maintenant paramétrable par variable d'environnement** (lignes 114-122). Fini le `# REPLACE THIS STRING` : `MCP_TRANSPORT=http|stdio` pilote `mcp.run()`, avec validation explicite — une valeur invalide (ou absente, qui retombe sur `"null"`) lève un `TypeError` clair au lieu d'échouer en silence. Cela répond au §V.2.5 (les deux transports) et au §V.2.1 (`uv run sandbox --mcp-server <URL>`). Vérifié : les deux valeurs démarrent, une valeur hors-ensemble lève l'erreur annoncée. Le `.env.example` documente la variable.

### ❌ Mauvais

1. **Le verdict repose toujours sur le code de retour du processus, donc `sys.exit(0)` suffit à faire passer tous les tests.** Vérifié — le code `import sys; sys.exit(0)` suivi d'une fonction renvoyant `None` reçoit `All test passed successfully !`. Même chose avec `os._exit(0)`. Ce n'est pas un scénario théorique de triche volontaire : un modèle qui écrit un `sys.exit()` défensif ou un `try/except: pass` autour de la logique obtient un faux positif, appelle `final_answer` avec un code faux, et la tâche est perdue à la validation. Il faut vérifier que l'assertion a réellement été évaluée — par exemple en faisant écrire au processus enfant un marqueur explicite après l'assertion, et en n'acceptant que ce marqueur comme preuve de succès. Ce point n'a pas bougé depuis le 14/08.

2. **Le timeout par test est devenu *pire* : `TIMEOUT_DELAY_SEC * len(TASK.test_list)` *par processus*** (ligne 97). Au 14/08 le cumul pire-cas était 10N s (N tests × 10 s). Désormais chaque test reçoit individuellement un budget de 10N s, soit un pire-cas total de **10N² s** — pour 5 tests, jusqu'à 250 s pour un *seul* appel d'outil, sur un budget global de 120 s (§VI.1.1). La modification semble vouloir borner le cumul mais applique la borne à chaque sous-processus au lieu du total : c'est un contresens qui aggrave exactement le défaut qu'il visait. Il faut soit un budget *global* partagé (arrêt dès que le cumul dépasse un plafond), soit un timeout constant par test **et** un plafond global — et la constante devrait venir de la configuration. Effet secondaire inchangé : `subprocess.run(timeout=)` ne tue que l'enfant direct — un code qui `fork()` laisse des orphelins sur l'hôte.

3. **L'isolation d'exécution manquante est désormais un écart face à un sandbox *existant*.** Voir Préambule point 2 : le code LLM continue de tourner sur l'hôte via `subprocess.run([sys.executable, ...])` (lignes 95-97), alors que `student/sandbox/` propose déjà le conteneur `network:none` + allowlist qu'il faudrait. C'est le point le plus grave : en soutenance, un correcteur lance `run_tests` avec un code qui lit `os.environ` ou écrit `/etc/…` et constate que le sandbox construit n'est pas sur le chemin. La moulinette de référence fait ce travail dans Docker (`interact.py:74`) ; aligner `run_tests` sur `SandboxContainer` est le premier geste.

4. **L'échec de test ne dit toujours pas *pourquoi* il échoue.** `proc.stdout` et `proc.stderr` sont capturés puis jetés ; seule la chaîne de l'assertion est renvoyée (ligne 103). Vérifié : `return a-b` (TypeError), `return [0,0]` (AssertionError) et un code ne définissant pas la fonction (NameError) produisent **exactement le même texte**. C'est le point qui coûtera le plus d'itérations : §V.1.3 impose un feedback explicite, et le budget est de 10 itérations et 6 000 tokens d'entrée cumulés (§VI.1.1). Renvoyer la dernière ligne de la traceback suffirait.

5. **Deux sources d'échec de `make lint` s'additionnent — dont une introduite par le correctif transport.** Le bloc DEBUG commenté (lignes 36-52) est toujours présent : `mcp_tools_mbpp.py:42` fait 111 caractères (E501), et le nouvel `if __name__ == "__main__"` (`mcp_tools_mbpp.py:119`) fait 115 caractères — vérifié : `make lint` casse aux deux lignes. Le correctif du §V.2.5 a donc réglé le transport tout en ajoutant une ligne hors norme. Deux constantes noms/nombres devraient être des constantes de module, et le bloc de debug doit disparaître (c'est du code mort).

### 🟡 Points de conception à trancher (hors comptage)

- **Aucune ressource ni prompt MCP n'est exposée.** Vérifié : `resources/list` → `[]`, `prompts/list` → `[]`. Le §V.2.5 énumère pourtant « MCP tools, resources, **and prompts** must be exposed ». Peu coûteux à combler côté MBPP (une ressource `mbpp://task` exposant l'énoncé, un prompt de résolution), c'est une ligne du barème.
- **La tâche n'est injectable qu'au démarrage, par variable d'environnement.** Rien dans le schéma de l'outil ne révèle cette dépendance : un correcteur qui lance le serveur à la main sans `MBPP_TASK_JSON` voit un `run_tests` qui échoue systématiquement sans indice sur la cause (le message d'erreur le dit, mais il faut lancer l'outil pour le lire). Un `--task-file` en argument de ligne de commande (en complément de l'env var) rendrait le serveur testable indépendamment, ce que le §V.5 exige pour les outils obligatoires.
- **Le numéro de ligne du `SyntaxError` est décalé.** `compile()` reçoit `f"{imports}\n\n{code}"` (ligne 82), donc la ligne rapportée est celle du texte concaténé, pas celle du code du LLM — décalage de +2 minimum, +2+len(test_imports) sinon. Vérifié : une erreur en ligne 1 du code soumis est annoncée « at line 3 ». Corriger en soustrayant l'offset avant de formater le message.
- **Un test qui passe ici ne garantit pas la validation.** La moulinette valide avec `skip_first_k_tests=0` (`moulinette/__main__.py:193`), c'est-à-dire **tous** les tests, alors que le `task.json` dumpé ne contient que `test_list[1:]` (`interact.py:210-211`). Un `success=True` fondé sur le seul verdict de `run_tests` est structurellement optimiste, et toute solution « collée » aux cas visibles sera prise en défaut — la garde-fou §VI.4.1 contre les solutions mémorisées. À dire dans le system prompt.
- **Divergence de version d'interpréteur.** `run_tests` exécute avec `sys.executable` (3.10, celui du projet) ; la moulinette valide dans `python:3.11-slim`. Rare mais réel comme source d'écart.

---

## `student/data_models/mbpp_task.py`

### ✅ Bon

1. **Correspondance champ par champ avec le contrat** (`moulinette/models_public.py:61-70`) : `task_id: int`, `task_definition`, `function_definition`, `test_imports`, `test_list` — mêmes noms, mêmes types, mêmes défauts. C'est ce qui permet à `mcp_tools_mbpp.py` de valider directement le JSON produit par `moulinette_eval dump mbpp` sans couche d'adaptation, vérifiable en 10 secondes par un correcteur qui diffe les deux fichiers.

2. **`default_factory=list` sur les deux champs de tests** — un `task.json` sans `test_imports` (cas majoritaire : la tâche 282 archivée a `"test_imports": []`) se parse sans cas particulier, et l'usage de `default_factory` plutôt que `= []` évite le piège classique du défaut mutable partagé entre instances.

3. **Les quatre champs porteurs de sens sont obligatoires (`...`)** — un `task.json` tronqué lève une `ValidationError` au chargement au lieu de produire un objet à moitié vide. C'est précisément ce qui donne du sens au `except ValidationError → TASK = None` du serveur MCP : sans obligation sur les champs, ce garde-fou ne se déclencherait jamais et l'outil tournerait sur une tâche fantôme.

4. **Syntaxe `list[str]` (PEP 585) et non `List[str]`** — cohérent avec `requires-python = "==3.10.*"` du `pyproject.toml`, et évite les imports `typing` que le fichier de référence traîne pour cause de compatibilité descendante. Le fichier étudiant est ici plus propre que le fichier fourni.

5. **Docstring qui référence le §V.3 et déclare explicitement le miroir** — la traçabilité vers le sujet est une attente répétée du §VI.4 (« Code quality, robustness »), et un correcteur qui cherche « où sont les modèles imposés » trouve la réponse dès la première ligne du fichier.

### ❌ Mauvais

1. **Le champ `function_definition` n'est toujours utilisé nulle part.** C'est pourtant la donnée la plus utile : le nom exact et la signature que la solution doit respecter (`def sub_list(nums1,nums2):`). Deux usages immédiats restent de côté — l'ancrer dans le system prompt pour que le modèle ne renomme pas la fonction, et vérifier dans `run_tests` que le code soumis définit bien ce nom, ce qui donnerait un message autrement plus exploitable que le `NameError` muet actuel (cf. point ❌4 du serveur MCP).

2. **Aucune contrainte au-delà du typage.** `task_id` peut être négatif, `test_list` peut être vide. Ce second cas n'est plus un faux positif à l'exécution (le serveur le garde désormais, cf. ✅2), mais il reste plus propre de le détecter **au chargement** : `Field(min_length=1)` sur `test_list` déplacerait la détection là où elle est diagnosticable, plutôt que de laisser le serveur faire une faveur à un `task.json` hors contrat.

3. **Copie manuelle du contrat, sans garde anti-dérive.** Rien ne vérifie que ce fichier reste aligné sur `moulinette/models_public.py`. Si la moulinette évolue, l'écart ne se manifestera qu'à l'examen. Un test unique comparant `MBPPTaskInput.model_json_schema()` à celui du modèle de référence transforme un risque silencieux en échec de CI.

4. **Aucun accesseur dérivé.** `mcp_tools_mbpp.py:80` fait déjà `"\n".join(TASK.test_imports)` à la main ; le futur constructeur de prompt refera le même travail pour `test_list`, et probablement différemment. Une propriété `test_preamble` / `public_tests_block` sur le modèle centralise la mise en forme et garantit que le LLM voit exactement ce que `run_tests` exécute — un écart entre les deux est une source d'itérations perdues difficile à diagnostiquer.

---

## `student/data_models/step_metrics.py`

### ✅ Bon

1. **Les 11 champs du §V.3.3 sont présents, aux bons noms et bons types** — `step`, `input_tokens`, `output_tokens`, `request_time_ms`, `api_url`, `model_name`, `llm_output`, `sandbox_input`, `sandbox_output`, `retries`, `timestamp`. C'est ce tableau que le §VI.4.1 désigne comme le support de la traçabilité du raisonnement ; un champ manquant n'est pas une imprécision de forme, c'est la preuve d'absence de contournement qui disparaît.

2. **Défauts sur les champs de traçabilité, obligation sur les champs de mesure.** `llm_output`, `sandbox_input`, `sandbox_output`, `api_url`, `model_name`, `retries` ont un défaut ; `step`, `input_tokens`, `output_tokens`, `request_time_ms` non. La ligne est tracée au bon endroit : une étape sans exécution sandbox reste enregistrable (§IV.1, aucune erreur ne doit faire tomber l'agent), mais on ne peut pas construire une étape en « oubliant » de mesurer la latence ou les tokens — or ce sont exactement les grandeurs que le §IV.2 rend obligatoires et que la moulinette contrôle.

3. **`request_time_ms: float` requis plutôt que défaut à 0.0** — un défaut aurait rendu le suivi de latence facultatif en pratique, alors que la fiabilité provider (temps de réponse moyen) est une section imposée du `BENCHMARK_REPORT.md` (§V.7 pt.3). Le modèle force la collecte à la source.

4. **`timestamp` en `default_factory` posé à la construction** — la chronologie est capturée sans effort côté appelant, et c'est elle qui rend calculables *a posteriori* les métriques intermédiaires du §V.7 pt.4. Sans horodatage par étape, ces analyses se refont à la main ou pas du tout.

5. **`retries` modélisé par étape et non seulement en total** — le §VI.1.3 interdit tout retry pendant l'examen, et le §V.7 pt.3 demande un décompte de retries par modèle. Avoir la granularité par étape permet de servir les deux usages ; l'agrégat se recalcule, l'inverse non.

### ❌ Mauvais

1. **Rien ne modélise les limites que ces métriques servent à respecter.** Les plafonds MBPP (10 itérations, 6 000 tokens d'entrée, 1 500 de sortie, 120 s — §VI.1.1) sont cumulatifs sur la tâche, et la moulinette les vérifie **après coup** (`MetricsValidationResult.validate_solution`). L'agent, lui, a besoin de la vérification **avant** d'envoyer la requête suivante. La moulinette expose un `MetricsLimits` (`moulinette/models.py`) ; il n'a pas d'équivalent côté étudiant. C'est d'autant plus urgent que `student/agent_core/` promet une boucle (« driven by … a limits config ») dont la limite n'est, encore une fois, que documentée.

2. **Aucune distinction entre « 0 token » et « usage non rapporté ».** Les deux compteurs sont des `int` sans `Optional` ni sentinelle. Tous les providers gratuits ne renvoient pas le bloc `usage` (souvent absent en streaming) : le code d'intégration n'aura d'autre choix que d'écrire 0, ce qui **sous-estime** le cumul. La direction de l'erreur est la mauvaise — on croit respecter la limite alors qu'on la dépasse, et c'est la moulinette qui le découvre. Le §VI précise que les tokens de raisonnement comptent dans la limite, ce qui aggrave l'écart sur les modèles « reasoning ».

3. **`step` n'a pas de contrainte `ge=1` alors que sa description dit « 1-indexed ».** La description est de la documentation, pas une validation. Un décalage 0-indexed passerait silencieusement et fausserait toutes les métriques intermédiaires du §V.7 ainsi que la lecture du log. `Field(..., ge=1)` fait tenir la promesse.

4. **Aucune politique de troncature sur `llm_output` / `sandbox_output`.** Le §V.1.3 exige qu'une sortie tronquée pour cause de taille soit **signalée explicitement** au LLM. Ici les champs stockent la chaîne brute : rien ne tronque, rien ne marque qu'on a tronqué. Deux conséquences — `solution.json` peut gonfler sans borne, et le jour où la troncature sera implémentée dans la boucle, elle n'aura aucun endroit où le déclarer. Un champ booléen `truncated` (ou un suffixe normalisé) doit être décidé maintenant, pendant que le format est encore libre.

---

## `student/data_models/solution.py`

### ✅ Bon

1. **Structure identique au contrat, avec `steps: list[StepMetrics]` typé sur le vrai modèle** — la validation de `solution.json` par la moulinette contrôle en une passe l'enveloppe *et* chaque étape. Un `list[dict]` aurait laissé passer des étapes malformées jusqu'à l'analyse post-mortem.

2. **`error: str | None = None` : le chemin d'échec a une forme définie.** C'est ce qui permet à un agent qui abandonne (limite d'itérations atteinte, provider indisponible) de produire quand même un `solution.json` valide avec `success=False` et une cause lisible, au lieu de crasher. Le §IV.1 est explicite : « crashes during evaluation will result in failure » — un échec propre et documenté n'est pas la même chose qu'un crash.

3. **`system_prompt` présent.** Le §VI.4.1 en fait l'artefact de traçabilité qui prouve que l'agent n'a pas récupéré une solution mémorisée ou externe, et toute violation vaut 0. Le champ apparaît à une position différente dans le snippet du §V.3 et dans celui du §VI, ce qui le fait fréquemment oublier ; il est là.

4. **`task_id: str` conservé, alors que `MBPPTaskInput.task_id` est un `int`.** L'incohérence apparente est celle du contrat, pas du code : la moulinette écrit un `int` dans `task.json` et refait `int(task.task_id)` de son côté à la validation. Résister à l'envie de « corriger » le type est le bon choix — c'est le genre de divergence unilatérale qui casse une validation le jour de l'examen.

5. **Docstring qui nomme le fichier de sortie et ce que la moulinette en fait** — le lecteur sait immédiatement que ce modèle n'est pas une structure interne mais une interface externe, donc qu'on ne la modifie pas librement.

### ❌ Mauvais

1. **`system_prompt` a un défaut vide alors que le sujet le rend obligatoire.** Le §V.4.2 le liste comme requis « pour une traçabilité complète du raisonnement », et le §VI.4.1 fait de cette traçabilité la pièce à conviction en cas de suspicion de solution mémorisée — sanction : 0. Avec `default=""`, un bug de câblage dans la boucle produit un `solution.json` parfaitement valide et totalement dépourvu de provenance, sans qu'aucune erreur ne soit levée. C'est le seul champ où être **plus strict** que le contrat ne coûte rien et supprime un risque à sanction maximale.

2. **Aucune validation croisée entre les totaux et les étapes.** Rien ne vérifie `total_input_tokens == sum(s.input_tokens for s in steps)`, ni `iterations == len(steps)`, ni `total_requests >= iterations`. Or la moulinette contrôle les **totaux** (`_print_metrics` lit `solution.total_*`) sans jamais les recouper avec `steps` : une erreur de comptabilité passe donc la validation, mais fausse toute l'analyse du `BENCHMARK_REPORT.md` (§V.7). Un `@model_validator(mode="after")` de six lignes rend l'incohérence impossible.

3. **`benchmark: str` libre plutôt que `Literal["mbpp", "swebench"]`.** Une faute de frappe (`"MBPP"`, `"mbpp "`) n'est détectée par rien côté étudiant. Côté moulinette, `_get_limits()` fait `sys.exit(1)` sur un benchmark inconnu : la tâche est perdue à la toute dernière étape, après avoir consommé le budget complet. Un `Literal` déplace l'échec à la construction de l'objet, c'est-à-dire avant. (L'ajout récent de `SWEBenchTaskInput` rend le couple `Literal["mbpp","swebench"]` plus pressant encore : le champ `benchmark` n'existera plus pour rien.)

4. **`success` n'est rattaché à aucune source de vérité.** Le champ est documenté « whether the agent believes it solved the task ». Combiné aux faux positifs restants de `run_tests` (`sys.exit(0)`) et au test caché rejoué à la validation (`skip_first_k_tests=0`), c'est le mode de défaillance le plus probable de toute la partie MBPP : l'agent se déclare gagnant et la moulinette dit non. Il faut décider et écrire la règle — `success=True` seulement si le dernier `run_tests` a répondu succès **et** que `final_answer` a été appelé avec ce code exact — plutôt que de laisser la boucle en décider au cas par cas.

5. **Aucun utilitaire d'écriture.** Le §V.3.1 impose un `--output ../cache/mbpp_solution.json` dont le répertoire parent n'existe pas forcément — la moulinette, elle, fait `output_path.parent.mkdir(parents=True, exist_ok=True)` avant d'écrire. Il manque le pendant côté étudiant (création du parent, `indent=2`, écriture atomique via fichier temporaire + `rename`). Un `solution.json` à moitié écrit parce que le processus a été interrompu, c'est une tâche perdue pour une raison sans rapport avec la qualité de l'agent.

---

## `student/data_models/__init__.py`

### ✅ Bon

1. **Point d'entrée unique et stable** — `from student.data_models import MBPPTaskInput` (déjà utilisé en `mcp_tools_mbpp.py:17`) découple les consommateurs du découpage en fichiers. Le paquet s'est élargi proprement avec `SWEBenchTaskInput` (cf. §V.4) sans toucher à l'interface existante.
2. **`__all__` explicite** — l'API publique du paquet est déclarée, pas déduite ; linters, `import *` et vérificateurs de types s'accordent sur la même liste.
3. **Le docstring justifie une décision d'architecture réelle** : `SandboxConfig` est délibérément hors de ce paquet, parce qu'il configure le sandbox et ne fait pas partie du contrat d'évaluation. C'est exactement le type de choix que le §VI.4 demande de savoir défendre, écrit à l'endroit où un correcteur ira le chercher — d'autant que le sandbox a désormais une vraie existence (`student/sandbox/config.py`), ce qui rend la justification encore plus solide.
4. **Un modèle par fichier plutôt qu'un `models.py` monolithique** — les modèles §V.3 et §V.4 restent séparément lisibles et diffables, et le fichier partagé (`step_metrics.py`) apparaît explicitement comme partagé.

### ❌ Mauvais

1. **La contradiction avec `student/agent_core/schemas.py` persiste — et s'aggrave avec la construction d'`agent_core/`.** `agent_core/schemas.py` affirme dans son docstring héberger `StepMetrics` et `SolutionOutput`, et placer `MBPPTaskInput`/`SWEBenchTaskInput` « dans leurs paquets `agent_mbpp`/`agent_swebench` respectifs ». Les quatre modèles sont en réalité dans `data_models`, et `agent_mbpp`/`agent_swebench` n'existent même plus. Deux fichiers décrivent donc deux architectures incompatibles, et le stub n'a plus aucune raison d'exister — d'autant que `agent_core/` est maintenant le cœur partagé affiché au §IV.2. En soutenance, où l'architecture est notée (§VI.4), ce fichier oriente le correcteur vers une question à laquelle il n'y a pas de bonne réponse : soit il cède (les modèles « revendiqués » ailleurs), soit il pointe vers des packages absents.

2. **Deux racines d'import incompatibles cohabitent dans le dépôt.** Ce paquet s'auto-importe en absolu (`from student.data_models.mbpp_task import ...`), donc il n'existe que sous le nom `student.data_models` ; `student/sandbox/` importe au contraire `sandbox.*` en top-level (`cli.py:17`), parce que `pyproject.toml` mappe `student/sandbox` → `sandbox` à la construction du wheel. Conséquence mesurable : mypy refuse d'analyser l'arbre (vérifié — `Source file found twice under different module names: "data_models" and "student.data_models"`), donc `make lint-strict` ne couvre pas ces fichiers. Des imports relatifs (`from .mbpp_task import ...`) suppriment la moitié du problème ; il reste à trancher une convention unique pour tout `student/`.

3. **`student/` n'a pas d'`__init__.py`** — c'est un paquet-espace-de-noms implicite qui ne fonctionne que parce que `sys.path[0]` est le répertoire du script lancé (vérifié : l'import passe depuis n'importe quel cwd tant que `mcp_tools_mbpp.py` est lancé par son chemin). Ça tient aujourd'hui, mais ça repose sur une propriété du lanceur, pas sur une déclaration du projet — et c'est la cause directe du point précédent.

---

## Récapitulatif de conformité §V.3

| Exigence | Réf. | État |
|---|---|---|
| CLI `python -m agent_mbpp` (`--task-file`, `--output`, `--model-name`, `--provider-url`) | §V.3.1 | ❌ Répertoire supprimé + toujours déclaré dans `pyproject.toml` → wheel cassé |
| Chargement de tâche + exécution agent | §V.3.1 | ❌ Absent (`agent_core/loop.py` est un docstring) |
| Outil MCP `run_tests` | §V.3.2 | 🟡 Fonctionne ; `test_list` vide corrigé ; mais faux positif `sys.exit(0)` et feedback pauvre |
| Ressources et prompts MCP exposés | §V.2.5 | ❌ `resources/list` et `prompts/list` vides (vérifié) |
| Transports stdio **et** HTTP | §V.2.5 | ✅ `MCP_TRANSPORT` env var (mais la ligne de validation casse `make lint`) |
| `mcp_tools_mbpp.py` à la racine | §V.2.5 | ✅ |
| Modèle `MBPPTaskInput` | §V.3.3 | ✅ Conforme au contrat |
| Modèle `StepMetrics` | §V.3.3 | ✅ Conforme au contrat |
| Modèle `SolutionOutput` | §V.3.3 | ✅ Conforme (`system_prompt` optionnel à durcir) |
| `max_iterations` configurable | §V.3.4 | ❌ Absent |
| Respect des limites cumulées (10 it. / 6 000 / 1 500 / 120 s) | §VI.1.1 | ❌ Aucun mécanisme côté étudiant |
| Code LLM exécuté dans le sandbox | §IV.1 | ❌ `run_tests` exécute sur l'hôte (vérifié), malgré un sandbox construit |
| **Build du wheel (`packages` de `pyproject.toml`)** | §VI | ❌ Référence des packages `agent_mbpp`/`agent_swebench` absents |

---

## Priorités recommandées

Par ordre d'impact sur la note — **l'ordre a changé depuis le 14/08** :

1. **Réparer la déclaration de packages dans `pyproject.toml`** — retirer `student/agent_mbpp` et `student/agent_swebench` des `packages` (ou les recréer) et résoudre le conflit d'import racine (`student.*` vs `sandbox.*`). Sans ça, `pip install .` échoue et **aucune** des commandes du §V.3 ne peut être évaluée — c'est la condition de recevabilité même.
2. **Faire passer l'exécution des tests par le sandbox existant** — réutiliser `SandboxContainer` (`network:none`, allowlist, `mem_limit`) dans `run_tests`, au lieu de `subprocess.run(sys.executable)` sur l'hôte. Le sandbox est construit ; l'écart est maintenant un non-câblage, pas un manque. Sans ce point, un correcteur démontre l'exfiltration en direct.
3. **Corriger le timeout global** — remplacer `10 × len(test_list)` *par processus* par un budget global (le pire-cas actuel de 10N² s fait déborder le 120 s §VI.1.1 à partir de 3-4 tests).
4. **Supprimer les faux positifs restants** — preuve d'exécution de l'assertion (contre `sys.exit(0)`). Un faux positif se paie par une tâche entière, et le seuil MBPP est 4/5.
5. **Renvoyer la cause de l'échec** (dernière ligne de traceback) — le meilleur rapport gain/effort sur le budget de 10 itérations et 6 000 tokens.
6. **Écrire `agent_mbpp/__main__.py`** (ou équivalent dans `agent_core`) avec `max_iterations` configurable et un garde-fou sur les limites cumulées ; sans lui, aucune des trois commandes du §V.3.1 ne s'exécute.
7. **Nettoyage de conformité** : ressources/prompts MCP, suppression du bloc de debug commenté **et** de la ligne de transport hors norme (les deux cassent `make lint`), résolution de la contradiction `agent_core/schemas.py` ↔ `data_models/`.

---

*Méthode de vérification : serveur MCP lancé en stdio avec `MBPP_TASK_JSON` renseigné (tâche 282), séquence JSON-RPC `initialize` → `notifications/initialized` → `tools/list` / `resources/list` / `prompts/list` → appels `tools/call` couvrant code correct, TypeError, AssertionError, fonction absente, `sys.exit(0)`, écriture disque, `print` parasite, boucle infinie, `test_list` vide, tâche non chargée et argument manquant. État du dépôt à la révision : branche `feat/SWE_MCP_Server`, `student/agent_mbpp`/`student/agent_swebench` supprimés, `student/agent_core/` et `student/sandbox/` construits. Scripts de sondage non versionnés (répertoire temporaire de session).*

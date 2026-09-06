
# --- Colors ---

GREEN   := \033[0;32m
RED     := \033[0;31m
YELLOW  := \033[0;33m
BLUE    := \033[0;34m
MAGENTA := \033[0;35m
CYAN    := \033[0;36m
RESET   := \033[0m

ECHO    := echo -e

# --- Makefile config ---

LINT_CHECK=./student mcp_tools_mbpp.py mcp_tools_swebench.py
PYTHON=uv run python
PROJECT_START_DATE=2026-08-10
PROJECT_NAME=42 Agent Smith
AUTHOR=sousampere & keroberos68
GITHUB=KeroBeros68/42-Agent-Smith

# --- Rules ---

install:
	@printf "\033[2J\033[H"
	@printf "$(YELLOW)╔════════════════════════════════════════════════════════════════╗\n"
	@printf "$(YELLOW)║                                                                ║\n"
	@printf "$(YELLOW)║  44  44    2222    $(GREEN)Made by $(AUTHOR) $(YELLOW)\n"
	@printf "$(YELLOW)║  44  44   22  22   Project: $(CYAN)$(PROJECT_NAME) $(YELLOW)\n"
	@printf "$(YELLOW)║  444444      22    Started in: $(CYAN)$(PROJECT_START_DATE) $(YELLOW)\n"
	@printf "$(YELLOW)║      44     22     Github: $(CYAN)$(GITHUB) $(YELLOW)\n"
	@printf "$(YELLOW)║      44   222222                                               ║\n"
	@printf "$(YELLOW)║                                                                ║\n"
	@printf "$(YELLOW)╚════════════════════════════════════════════════════════════════╝\n"
	@printf "\033[3;66H║"
	@printf "\033[4;66H║"
	@printf "\033[5;66H║"
	@printf "\033[6;66H║"
	@printf "\033[7;66H║"
	@printf "\033[8;66H║"
	@printf "\033[9;80H\n"
	@printf "$(CYAN)[Installation]$(RESET) ➡️  Synchronizing uv\n"
	uv sync

lint: install
	$(PYTHON) -m flake8 $(LINT_CHECK)
	$(PYTHON) -m -m mypy $(LINT_CHECK) --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict: install
	$(PYTHON) -m flake8 $(LINT_CHECK)
	$(PYTHON) -m mypy $(LINT_CHECK) --strict

debug: install
	$(PYTHON) -m pdb -m $(LINT_CHECK)

# --- Tasks & Agent runs ---

MODEL        ?= deepseek/deepseek-v4-flash
BENCH        ?= mbpp
N            ?= 3
PROVIDER_URL ?=
CACHE_DIR    := cache

# Exports <PROVIDER>_API_KEY (derived from the provider/ prefix of $(MODEL))
# by reading .env directly — sourcing the whole file breaks on the JSON
# values it also holds (they contain braces).
define export_provider_key
PROVIDER_VAR=$$(echo "$(MODEL)" | cut -d'/' -f1 | tr 'a-z' 'A-Z')_API_KEY; \
KEY_VAL=$$(PV="$$PROVIDER_VAR" python3 -c "import re, os; c = open('.env').read(); m = re.search('^' + os.environ['PV'] + '=(.*)', c, re.MULTILINE); print(m.group(1) if m else '')"); \
export $$PROVIDER_VAR="$$KEY_VAL"
endef

# make task BENCH=mbpp OR make task BENCH=mbpp TASK_ID=282
# make task BENCH=swebench OR make task BENCH=swebench TASK_ID=django__django-11066
task:
	@printf "$(CYAN)[Task]$(RESET) ➡️  Generating one $(BENCH) task\n"
	@cd moulinette && uv run moulinette_eval dump $(BENCH) $(if $(TASK_ID),--task-id $(TASK_ID)) --output ../$(CACHE_DIR)/$(BENCH)_task.json

# make tasks BENCH=swebench N=5
tasks:
	@printf "$(CYAN)[Tasks]$(RESET) ➡️  Generating $(N) $(BENCH) tasks\n"
	@for i in $$(seq 1 $(N)); do \
		printf "$(CYAN)  -> task $$i/$(N)$(RESET)\n"; \
		(cd moulinette && uv run moulinette_eval dump $(BENCH) --output ../$(CACHE_DIR)/$(BENCH)_task_$$i.json) || exit 1; \
	done

# make run BENCH=mbpp
# make run BENCH=swebench MODEL=openrouter/minimax/minimax-m2.7:free PROVIDER_URL=https://openrouter.ai/api/v1
run:
	@printf "$(CYAN)[Run]$(RESET) ➡️  Running the agent on one $(BENCH) task\n"
	@$(export_provider_key); \
	cd student && uv run python -m agent_$(BENCH) \
		--task-file ../$(CACHE_DIR)/$(BENCH)_task.json \
		--output ../$(CACHE_DIR)/$(BENCH)_solution.json \
		--model-name "$(MODEL)" \
		$(if $(PROVIDER_URL),--provider-url "$(PROVIDER_URL)")

# make runs BENCH=swebench N=5 MODEL=openrouter/minimax/minimax-m2.7:free PROVIDER_URL=https://openrouter.ai/api/v1
runs:
	@printf "$(CYAN)[Runs]$(RESET) ➡️  Running the agent on $(N) $(BENCH) tasks\n"
	@$(export_provider_key); \
	for i in $$(seq 1 $(N)); do \
		printf "$(CYAN)  -> run $$i/$(N)$(RESET)\n"; \
		(cd student && uv run python -m agent_$(BENCH) \
			--task-file ../$(CACHE_DIR)/$(BENCH)_task_$$i.json \
			--output ../$(CACHE_DIR)/$(BENCH)_solution_$$i.json \
			--model-name "$(MODEL)" \
			$(if $(PROVIDER_URL),--provider-url "$(PROVIDER_URL)")) || exit 1; \
	done

.PHONY: install lint lint-strict debug task tasks run runs

PYTHON := .venv/bin/python3
PIP := .venv/bin/pip

.PHONY: install test-single-lead test-linkedin redraft reset-db schema api daily-run poll-replies run-campaigns send help

help:
	@echo "make install              - install Python deps"
	@echo "make schema               - reminder to run SQL in Supabase"
	@echo "make test-single-lead CITY=Miami  - run end-to-end test"
	@echo "make redraft LEAD_ID=xxx  - iterate on draft for one lead"
	@echo "make reset-db             - truncate leads + messages"
	@echo "make api                  - start FastAPI server on :8000"
	@echo "make daily-run            - run prospect/enrich/draft pipeline"
	@echo "make poll-replies         - poll AgentMail for new replies"
	@echo "make run-campaigns        - tick every active autonomous campaign"
	@echo "make send MESSAGE_ID=xxx  - send a single drafted message"
	@echo "make test-linkedin LEAD_ID=xxx KIND=invite [SEND=1] - smoke test LinkedIn channel"

install:
	$(PIP) install -r agent/requirements.txt
	$(PIP) install -e .

schema:
	@echo "Run agent/sql/schema.sql then agent/sql/seed.sql in Supabase SQL editor"

test-single-lead:
	@if [ -z "$(CITY)" ]; then echo "Usage: make test-single-lead CITY=Miami"; exit 1; fi
	$(PYTHON) scripts/test_single_lead.py --city $(CITY) --count 5

redraft:
	@if [ -z "$(LEAD_ID)" ]; then echo "Usage: make redraft LEAD_ID=xxx"; exit 1; fi
	$(PYTHON) scripts/redraft.py $(LEAD_ID)

reset-db:
	$(PYTHON) scripts/reset_db.py --confirm

api:
	$(PYTHON) scripts/run_api.py

daily-run:
	$(PYTHON) -m agent.src.main daily-run

poll-replies:
	$(PYTHON) -m agent.src.main poll-replies

run-campaigns:
	$(PYTHON) -m agent.src.main run-campaigns

send:
	@if [ -z "$(MESSAGE_ID)" ]; then echo "Usage: make send MESSAGE_ID=xxx"; exit 1; fi
	$(PYTHON) -m agent.src.main send --message-id $(MESSAGE_ID)

test-linkedin:
	@if [ -z "$(LEAD_ID)" ] || [ -z "$(KIND)" ]; then echo "Usage: make test-linkedin LEAD_ID=xxx KIND=invite|dm [SEND=1]"; exit 1; fi
	$(PYTHON) scripts/test_linkedin_send.py --lead-id $(LEAD_ID) --kind $(KIND) $(if $(SEND),--send,)

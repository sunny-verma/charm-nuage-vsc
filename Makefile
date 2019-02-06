#!/usr/bin/make

lint:
	@flake8 --exclude hooks/charmhelpers hooks
	@charm proof

bin/charm_helpers_sync.py:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py \
        > bin/charm_helpers_sync.py
	
sync: bin/charm_helpers_sync.py
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers.yaml

test:
	@# Bundletester expects unit tests here.
	@echo Starting unit tests...
	@$(PYTHON) /usr/bin/nosetests -v --nologcapture --with-coverage unit_tests

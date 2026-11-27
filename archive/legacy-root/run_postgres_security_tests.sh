#!/usr/bin/env sh
set -eu
: "${TEST_DATABASE_ADMIN_URL:?Set TEST_DATABASE_ADMIN_URL to a disposable PostgreSQL test database owner URL}"
: "${TEST_DATABASE_URL:?Set TEST_DATABASE_URL to the non-owner cfdt_juris_app runtime URL}"
python -m pytest -q backend/tests/test_postgres_rls_integration.py

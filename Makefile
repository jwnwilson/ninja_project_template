.PHONY: venv test lint
.DEFAULT_GOAL = help
.EXPORT_ALL_VARIABLES:

TF_VAR_docker_tag := latest
TF_VAR_environment=${ENVIRONMENT}
TF_VAR_ecr_api_url=${AWS_ACCOUNT}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com/{{project_slug}}_api
TF_VAR_aws_access_key=${AWS_ACCESS_KEY_ID}
TF_VAR_aws_secret_key=${AWS_SECRET_ACCESS_KEY}
TF_VAR_aws_region=${AWS_DEFAULT_REGION}

VENV := .venv
MKFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
VENV_DIR = $(MKFILE_DIR)$(VENV)
DJANGO_MANAGE_PY = PYTHONPATH=src uv run manage.py

# Setup commands
venv:
	@../../tools/bash_scripts/setup_env.sh

build: collectstatic venv
	docker compose build

collectstatic:
	$(DJANGO_MANAGE_PY) collectstatic --noinput

# DB management

db: docker_stop
	docker compose run --service-ports -d db 

db_migrate_pipeline:
	$(DJANGO_MANAGE_PY) migrate
	EXIT_CODE=$$?;\
    exit $$EXIT_CODE

db_migrate_local:
	$(DJANGO_MANAGE_PY) migrate

db_migrate_docker:
	docker compose run api bash -c "$(DJANGO_MANAGE_PY) migrate"

db_delete_data: 
	docker compose run db bash -c "rm -rf /var/lib/postgresql/data/*"

db_create_migration: 
	$(DJANGO_MANAGE_PY) makemigrations

docker_stop:
	@-bash -c "docker ps -aq | xargs docker stop | xargs docker rm"

down:
	docker compose down
	bash -c "docker ps -aq | xargs docker stop | xargs docker rm"
	
# Local Development
create_superuser:
	$(DJANGO_MANAGE_PY) createsuperuser

celery:
	docker compose run --service-ports -d celery 

db_celery:
	docker compose up -d db celery 

# Host API locally, loading local env file
run: down db_celery venv
	$(DJANGO_MANAGE_PY) runserver

# Host API locally, connect to cloud db. Still requires manual setting of DB_PASSWORD_SECRET_NAME in bastion.env
run_bastion: bastion venv
	$(DJANGO_MANAGE_PY) runserver

# Host API locally and run in docker
run_docker:
	docker compose up

# Testing commands

test: venv db
	@echo "Running unit tests"
	uv run pytest

coverage:
	@echo "Running unit tests"	
	uv run pytest --cov-report html	

lint:
	@TARGET_DIRS="src" bash ../../tools/bash_scripts/lint.sh 

lint_check: venv
	@TARGET_DIRS="src" bash ../../tools/bash_scripts/lint.sh --check

clean:
	@find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
	@find . -name 'test_db_*.sqlite3' -delete
	@find . -name '.coverage.*' -delete

tf_workspace:
	@cd infra/tf/aws/environment && \
	terraform workspace select -or-create=true $(ENVIRONMENT) 

tf_init:
	@echo "Initializing Terraform infra"
	@rm -rf ./infra/tf/aws/shared/.terraform
	@rm -rf ./infra/tf/aws/environment/.terraform
	cd infra/tf/aws/shared  && terraform init -input=false -upgrade
	cd infra/tf/aws/environment  && terraform init -input=false -upgrade

tf_setup: tf_init
	@echo "Applying Inital project Terraform infra"
	cd infra/tf/aws/shared && terraform workspace select -or-create=true default
	cd infra/tf/aws/shared && terraform apply

tf_plan:
	@echo "Planning Terraform infra"
	cd infra/tf/aws/shared  && terraform plan
	cd infra/tf/aws/environment && terraform plan

tf_apply:
	@echo "Applying Terraform infra"
	cd infra/tf/aws/shared && terraform apply
	cd infra/tf/aws/environment  && terraform apply

tf_apply_no_input:
	@echo "Applying Terraform infra"
	cd infra/tf/aws/shared && terraform apply -auto-approve
	cd infra/tf/aws/environment && terraform apply -auto-approve

tf_destroy:
	@echo "Destroying Terraform infra"
	cd infra/tf/aws/environment  && terraform destroy
	cd infra/tf/aws/shared  && terraform destroy

tf_refresh: tf_workspace
	@cd infra/tf/aws/environment && terraform refresh

tf_output: tf_workspace
	@cd infra/tf/aws/environment && terraform output -json

deploy: build tf_workspace
	PROJECT={{project_slug}} NO_INPUT=$(NO_INPUT) ENVIRONMENT=$(ENVIRONMENT) ../../tools/bash_scripts/deploy.sh 

bastion: venv
	@echo "Activating bastion port forwarding..."
	cd ../../ && \
	hextech bastion 
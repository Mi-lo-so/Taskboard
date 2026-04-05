# Taskboard

This project implements a simple AWS solution for storing tasks in AWS.

## Services

TODO

# Setup (developer environment)

From the project root, run the docker file to generate the image:

```bash
docker compose up -d
```

# Curl usage examples

Create a task:

```bash
curl --header "Content-Type: application/json" --request POST --data '{"title":"SomeTask"}' http://localhost:8000/tasks
```

Get tasks:

```bash
curl http://localhost:8000/tasks
```

Run formatting check with

``` bash
uv run ruff check  
```    

Set up the virtual environment to avoid messing with local environment
This isolation is important since different packages and projects use different package versions, etc,
So without isolating the project, the machine suffers conflicts.

This project uses `uv` to manage the virtual environment

```bash
uv venv
```

install/update dependencies

```bash
uv pip install -r pyproject.toml
```

Generate a uv lock file

```bash
uv pip compile pyproject.toml -o uv.lock
```

regenerate uv.lock

```bash
uv  uv.lock --upgrade
```

keep requirements.txt updated, since it's currently used by Docker file

```bash
uv pip compile pyproject.toml -o requirements.txt
```

Keep the lock file in sync going forward

```bash
uv pip sync uv.lock
```

```bash
uv sync
```

# edit .env with your DB credentials

alembic upgrade head

```bash
 poetry run alembic upgrade head        
```

Run migrations (requires a running Postgres, set DATABASE_URL in .env):

```bash                                                         
 cp .env.example .env           
```                        

Start the API locally:

```bash                                             
 uvicorn main:app --reload 
```

# Alembic

alembic upgrade head

Task model fields

     ┌──────────────────────────────────────────┬───────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐                                         
     │Field                                     │Type                                       │Notes                                                                │     
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤  
     │id                                        │Integer PK                                 │auto-increment                                                       │                                               
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │description                               │Text                                       │nullable                                                             │  
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │status                                    │Enum                                       │todo / in_progress / done, default todo                              │      
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │progress                                  │Integer                                    │0–100 (DB check constraint), default 0                               │    
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │created_at                                │DateTime(tz)                               │server default now()                                                 │  
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │updated_at                                │DateTime(tz)                               │server default now(), auto-updated                                   │   
     └──────────────────────────────────────────┴───────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘                                              
                                                                                                                                                                                                                 
     API endpoints                                                                                                                                                                                               
                                                                                                                                                                                                                 
     ┌───────────────────────────────────────┬────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────┐                                              
     │Method                                 │Path                                        │Description                                                            │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │GET                                    │/tasks/                                     │List tasks (paginated with skip/limit)                                 │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │POST                                   │/tasks/                                     │Create a task                                                          │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │GET                                    │/tasks/{id}                                 │Get a single task                                                      │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │PATCH                                  │/tasks/{id}                                 │Partially update a task                                                │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │DELETE                                 │/tasks/{id}                                 │Delete a task                                                          │                                              
     └───────────────────────────────────────┴────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┘                                              

# Deployment

Deploy to AWS (requires AWS CLI credentials + CDK bootstrap):

> After deploy, update DATABASE_URL in .env with the RDS endpoint from outputs

## CDK - deploy app

If you haven't done so already, install aws command line package with

```bash
npm install -g aws-cdk
```

### 1. Bootstrap (once per account/region)

```bash
cdk bootstrap --app 'uv run python infra/taskboard/stack.py' --require-approval never
```

TODO considering: cdk bootstrap --app 'uv run python infra/{{arg(name=\"stack\")}}/stack.py --require-approval never

#### 2. Deploy infrastructure

```bash
cdk deploy --app 'uv run python infra/taskboard/stack.py' --require-approval never
```                                                                                                                                            

#### 3. Push your image to ECR (URI is in the stack outputs)

```bash
ECR_URI=$(aws cloudformation describe-stacks --stack-name TaskBoardStack \                                                                                                              
--query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri'].OutputValue" \                                                                                                             
--output text)       
```                                                                                                                                                                 

```bash                                                                                                                                    
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $ECR_URI   
```                                                                                                                         

```bash                                                                                                                                                                                   
docker build -t $ECR_URI:latest .   
```

```bash
docker push $ECR_URI:latest  
```                                                                                               

# 4. Force ECS to pick up the new image

```bash
aws ecs update-service --cluster TaskBoardCluster  --service TaskBoardService --force-new-deployment    
```
